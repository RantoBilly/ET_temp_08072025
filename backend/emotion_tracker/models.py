from django.db import models
from django.db.models import Avg, Count, Sum
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime
import uuid


class Company(models.Model):
    """Modèle pour les entreprises"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Nom de l'entreprise")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Cluster(models.Model):
    """Modèle pour les clusters/pôles"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Nom du cluster")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='clusters')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cluster"
        verbose_name_plural = "Clusters"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"


class Service(models.Model):
    """Modèle pour les services/départements"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_name = models.CharField(max_length=255, verbose_name="Nom du service")
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='services', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='services')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['service_name']
    
    def __str__(self):
        return self.service_name


class Team(models.Model):
    """Modèle pour les équipes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_name = models.CharField(max_length=255, verbose_name="Nom de l'équipe")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='teams', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Équipe"
        verbose_name_plural = "Équipes"
        ordering = ['team_name']
    
    def __str__(self):
        return self.team_name


class Collaborator(AbstractUser):
    """Modèle étendu pour les collaborateurs (utilisateurs)"""
    ROLE_CHOICES = [
        ('employee', 'Employé'),
        ('manager', 'Manager'),
        ('director', 'Directeur'),
        ('pole_director', 'Directeur de Pôle'),
        ('admin', 'Administrateur'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaborator_id = models.CharField(max_length=50, unique=True, verbose_name="ID Collaborateur")
    first_name = models.CharField(max_length=150, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, verbose_name="Nom")
    email = models.EmailField(unique=True, verbose_name="Adresse email")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee', verbose_name="Rôle")
    
    # Relations hiérarchiques
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='collaborators')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='collaborators')
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='collaborators')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='collaborators')
    
    # Manager hiérarchique
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_collaborators')
    
    # Champs calculés pour les émotions
    emotion_today_morning = models.CharField(max_length=50, null=True, blank=True)
    emotion_today_evening = models.CharField(max_length=50, null=True, blank=True)
    emotion_this_week = models.CharField(max_length=50, null=True, blank=True)
    emotion_this_month = models.CharField(max_length=50, null=True, blank=True)
    emotion_degree_this_week = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    emotion_degree_this_month = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    # Métadonnées
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Champs requis par AbstractUser
    username = models.CharField(max_length=150, unique=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'collaborator_id']
    
    class Meta:
        verbose_name = "Collaborateur"
        verbose_name_plural = "Collaborateurs"
        ordering = ['last_name', 'first_name']

    def get_today_morning_emotion(self):
        """
        Récupère l'émotion du matin pour aujourd'hui
        """
        today = timezone.now().date()

        try:
            # Filtrer les émotions pour aujourd'hui, le matin
            today_morning_emotion = Emotion.objects.filter(
                collaborator=self,  # Lié au collaborateur actuel
                date=today,         # Date d'aujourd'hui
                date_period="Ce jour",  # Période du jour
                half_day=False      # Matin (half_day < 12h)
            ).first()  # Prendre la première émotion correspondante

            # Retourner l'émotion ou None si pas d'émotion trouvée
            return today_morning_emotion
        except Emotion.DoesNotExist:
            return None

    def get_today_evening_emotion(self):
        """
        Récupère l'émotion du soir pour aujourd'hui
        """
        today = timezone.now().date()

        try:
            # Filtrer les émotions pour aujourd'hui, le matin
            today_morning_emotion = Emotion.objects.filter(
                collaborator=self,  # Lié au collaborateur actuel
                date=today,         # Date d'aujourd'hui
                date_period="Ce jour",  # Période du jour
                half_day=True      # Soir (half_day >= 12h)
            ).first()  # Prendre la première émotion correspondante

            # Retourner l'émotion ou None si pas d'émotion trouvée
            return today_evening_emotion
        except Emotion.DoesNotExist:
            return None

    def calculate_emotion_degree_this_week(self):
        """
        Calcule la somme des degrés d'émotion pour la semaine en cours
        """

        # Obtenir la date de début et de fin de la semaine en cours
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=6)

        # Filtrer les émotions de la semaine en cours pour ce collaborateur
        weekly_emotions = Emotion.objects.filter(
            collaborator=self,
            date__range=[start_of_week, end_of_week]
        )

        # Calculer la somme des degrés d'émotion
        total_emotion_degree = weekly_emotions.aggregate(
            total_degree=Sum('emotion_degree')
        )['total_degree'] or 0

        return total_emotion_degree

    def calculate_emotion_degree_this_month(self):
        """
        Calcule la somme des degrés d'émotion pour le mois en cours
        """

        # Obtenir la date de début et de fin du mois en cours
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)

        # Filtrer les émotions du mois en cours pour ce collaborateur
        monthly_emotions = Emotion.objects.filter(
            collaborator=self,
            date__range=[start_of_month, end_of_month]
        )

        # Calculer la somme des degrés d'émotion
        total_emotion_degree = monthly_emotions.aggregate(
            total_degree=Sum('emotion_degree')
        )['total_degree'] or 0

        return total_emotion_degree
    
    def save(self, *args, **kwargs):

        # Mettre à jour emotion_today_morning lors de la sauvegarde
        morning_emotion = self.get_today_morning_emotion()

        if morning_emotion:
            self.emotion_today_morning = morning_emotion.emotion_type
        else:
            self.emotion_today_morning = None

        # Récupérer et mettre à jour l'émotion du soir
        evening_emotion = self.get_today_evening_emotion()

        if evening_emotion:
            self.emotion_today_evening = evening_emotion.emotion_type
        else:
            self.emotion_today_evening = None

        # Calculer et mettre à jour le degré d'émotion pour la semaine
        self.emotion_degree_this_week = self.calculate_emotion_degree_this_week()

        # Déterminer emotion_this_week en fonction de emotion_degree_this_week
        if self.emotion_degree_this_week is not None:
            if self.emotion_degree_this_week <= -5:
                self.emotion_this_week = "Angry"
            elif self.emotion_degree_this_week <= -2:
                self.emotion_this_week = "Anxious"
            elif self.emotion_degree_this_week <= -1:
                self.emotion_this_week = "Sad"
            elif self.emotion_degree_this_week == 0:
                self.emotion_this_week = "Neutral"
            elif self.emotion_degree_this_week <= 5:
                self.emotion_this_week = "Happy"
            else:
                self.emotion_this_week = "Excited"
        else:
            self.emotion_this_week = None

        # Calculer et mettre à jour le degré d'émotion pour le mois
        self.emotion_degree_this_month = self.calculate_emotion_degree_this_month()

        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return self.full_name


class EmotionType(models.Model):
    """Modèle pour les types d'émotions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de l'émotion")
    emotion = models.CharField(max_length=50, verbose_name="Code émotion")
    degree = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="Degré")
    emotions = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Type d'émotion"
        verbose_name_plural = "Types d'émotions"
        ordering = ['degree', 'name']

    def save(self, *args, **kwargs):
        # Calcul du degree en fonction du type d'émotion
        emotion_degree_mapping = {
            'happy': 1,
            'Sad': -1,
            'Neutral': 0,
            'Angry': -5,
            'Excited': 5,
            'Anxious': -2
        }

        # Utiliser le type d'émotion pour déterminer le degree
        self.degree = emotion_degree_mapping.get(self.emotion_type, 0)  # 0 par défaut si non trouvé

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} (Degré: {self.degree})"


class Emotion(models.Model):
    """Modèle principal pour les déclarations d'émotions"""
    PERIOD_CHOICES = [
        ('morning', 'Matin'),
        ('evening', 'Soir'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emotion_id = models.CharField(max_length=100, unique=True, verbose_name="ID Émotion")
    collaborator = models.ForeignKey(Collaborator, on_delete=models.CASCADE, related_name='emotions')
    emotion_type = models.ForeignKey(EmotionType, on_delete=models.CASCADE, related_name='emotion_entries')
    
    # Informations temporelles
    date = models.DateField(verbose_name="Date")
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, verbose_name="Période")
    week_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(53)], verbose_name="Numéro de semaine")
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)], verbose_name="Mois")
    year = models.IntegerField(verbose_name="Année")
    
    # Informations contextuelles
    team = models.CharField(max_length=255, blank=True, verbose_name="Équipe")
    company = models.CharField(max_length=255, blank=True, verbose_name="Entreprise")
    cluster = models.CharField(max_length=255, blank=True, verbose_name="Cluster")
    full_name = models.CharField(max_length=300, blank=True, verbose_name="Nom complet")
    
    # Données calculées et insights
    weekly_emotion_summary = models.TextField(blank=True, verbose_name="Résumé émotionnel hebdomadaire")
    monthly_emotion_insights = models.TextField(blank=True, verbose_name="Insights émotionnels mensuels")
    emotion_degree = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="Degré d'émotion")
    
    # Champs additionnels
    creation_date = models.DateTimeField(auto_now_add=True)
    half_day = models.BooleanField(default=False, verbose_name="Demi-journée")
    date_period = models.CharField(max_length=20, blank=True, verbose_name="Période de date")
    emotion_illustration = models.TextField(blank=True, verbose_name="Illustration émotion")
    
    # Commentaire optionnel
    comment = models.TextField(blank=True, null=True, verbose_name="Commentaire")
    
    class Meta:
        verbose_name = "Déclaration d'émotion"
        verbose_name_plural = "Déclarations d'émotions"
        ordering = ['-date', '-creation_date']
        unique_together = ['collaborator', 'date', 'period']
        indexes = [
            models.Index(fields=['date', 'period']),
            models.Index(fields=['collaborator', 'date']),
            models.Index(fields=['week_number', 'year']),
            models.Index(fields=['month', 'year']),
        ]

    def calculate_weekly_emotion_summary(self):
        """
        Calcule un résumé des émotions pour la semaine en cours
        """

        # Obtenir la date de début et de fin de la semaine en cours
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=6)

        # Filtrer les émotions de la semaine en cours pour ce collaborateur
        weekly_emotions = Emotion.objects.filter(
            collaborator=self.collaborator,
            date__range=[start_of_week, end_of_week]
        )

        # Calculer les statistiques
        total_emotions = weekly_emotions.count()
        avg_emotion_degree = weekly_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg'] or 0

        # Compter les types d'émotions
        emotion_type_counts = weekly_emotions.values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        )

        # Construire le résumé
        summary = {
            'total_emotions': total_emotions,
            'average_emotion_degree': round(avg_emotion_degree, 2),
            'emotion_type_breakdown': {
                item['emotion_type__emotion_type']: item['count'] 
                for item in emotion_type_counts
            }
        }

        self.weekly_emotion_summary = json.dumps(summary)
        return summary

    def calculate_monthly_emotion_insights(self):
        """
        Calcule des insights émotionnels pour le mois en cours
        """

        # Obtenir la date de début et de fin du mois en cours
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)

        # Filtrer les émotions du mois en cours pour ce collaborateur
        monthly_emotions = Emotion.objects.filter(
            collaborator=self.collaborator,
            date__range=[start_of_month, end_of_month]
        )

        # Calculs statistiques
        total_emotions = monthly_emotions.count()
        avg_emotion_degree = monthly_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg'] or 0

        # Identifier les tendances émotionnelles
        emotion_trends = {
            'most_frequent_emotion': monthly_emotions.values('emotion_type__emotion_type')
                .annotate(count=Count('emotion_type__emotion_type'))
                .order_by('-count')
                .first(),
            'highest_emotion_degree': monthly_emotions.order_by('-emotion_degree').first(),
            'lowest_emotion_degree': monthly_emotions.order_by('emotion_degree').first()
        }

        # Calcul de la progression émotionnelle
        emotion_progression = self.calculate_emotion_progression(monthly_emotions)

        # Construire les insights
        insights = {
            'total_emotions': total_emotions,
            'average_emotion_degree': round(avg_emotion_degree, 2),
            'emotion_trends': {
                'most_frequent_emotion': emotion_trends['most_frequent_emotion']['emotion_type__emotion_type'] 
                    if emotion_trends['most_frequent_emotion'] else None,
                'highest_emotion': emotion_trends['highest_emotion_degree'].emotion_type.emotion_type 
                    if emotion_trends['highest_emotion_degree'] else None,
                'lowest_emotion': emotion_trends['lowest_emotion_degree'].emotion_type.emotion_type 
                    if emotion_trends['lowest_emotion_degree'] else None
            },
            'emotion_progression': emotion_progression
        }

        self.monthly_emotion_insights = json.dumps(insights)
        return insights

    def calculate_emotion_progression(self, monthly_emotions):
        """
        Calcule la progression des émotions sur le mois
        """

        progression = []
        for emotion in monthly_emotions.order_by('date'):
            progression.append({
                'date': emotion.date.isoformat(),
                'emotion_type': emotion.emotion_type.emotion_type,
                'emotion_degree': emotion.emotion_degree
            })
        return progression
    
    def save(self, *args, **kwargs):

        # Calcul de emotion_degree basé sur le type d'émotion
        if self.emotion_type:
            emotion_degree_mapping = {
            'happy': 1,
            'Sad': -1,
            'Neutral': 0,
            'Angry': -5,
            'Excited': 5,
            'Anxious': -2
            }

            # Récupérer le degree du type d'émotion
            self.emotion_degree = emotion_degree_mapping.get(self.emotion_type.emotion_type, 0)
        else:
            # Si pas de type d'émotion, mettre à 0 par défaut
            self.emotion_degree = 0

        # Calcul de date_period
        today = timezone.now().date()
        if self.date == today:
            self.date_period = "Ce jour"
        elif self.date.isocalendar()[1] == today.isocalendar()[1] and self.date.year == today.year:
            self.date_period = "cette semaine"
        elif self.date.month == today.month and self.date.year == today.year:
            self.date_period = "ce mois"
        else:
            self.date_period = "cette année"

        # Half_day
        current_time = timezone.now().time()
        self.half_day = current_time.hour >= 12

        if not self.emotion_id:
            self.emotion_id = f"{self.collaborator.collaborator_id}-{self.date}-{self.period}"
        
        # Auto-remplir les champs calculés
        if self.date:
            self.week_number = self.date.isocalendar()[1]
            self.month = self.date.month
            self.year = self.date.year
        
        if self.collaborator:
            self.full_name = self.collaborator.full_name
            if self.collaborator.team:
                self.team = self.collaborator.team.team_name
            if self.collaborator.company:
                self.company = self.collaborator.company.name
            if self.collaborator.cluster:
                self.cluster = self.collaborator.cluster.name

        # Calculer les résumés et insights lors de la sauvegarde
        self.calculate_weekly_emotion_summary()
        self.calculate_monthly_emotion_insights()
 
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.collaborator.full_name} - {self.emotion_type.name} - {self.date} ({self.period})"


class EmotionTrend(models.Model):
    """Modèle pour les tendances émotionnelles"""
    TREND_PERIOD_CHOICES = [
        ('weekly', 'Hebdomadaire'),
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relations
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='emotion_trends', null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='emotion_trends', null=True, blank=True)
    
    # Données de tendance
    weekly_emotion_trend = models.JSONField(default=dict, verbose_name="Tendance émotionnelle hebdomadaire")
    monthly_emotion_summary = models.JSONField(default=dict, verbose_name="Résumé émotionnel mensuel")
    
    # Période et métadonnées
    period_type = models.CharField(max_length=20, choices=TREND_PERIOD_CHOICES, verbose_name="Type de période")
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    
    # Données calculées
    average_emotion_score = models.FloatField(null=True, blank=True, verbose_name="Score émotionnel moyen")
    dominant_emotion = models.CharField(max_length=100, blank=True, verbose_name="Émotion dominante")
    participation_rate = models.FloatField(null=True, blank=True, verbose_name="Taux de participation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tendance émotionnelle"
        verbose_name_plural = "Tendances émotionnelles"
        ordering = ['-start_date']
        unique_together = ['team', 'service', 'period_type', 'start_date']
    
    def __str__(self):
        entity = self.team.team_name if self.team else self.service.service_name if self.service else "Global"
        return f"Tendance {self.period_type} - {entity} - {self.start_date}"


class Alert(models.Model):
    """Modèle pour les alertes et notifications"""
    ALERT_TYPE_CHOICES = [
        ('consecutive_negative', 'Émotions négatives consécutives'),
        ('low_team_morale', 'Moral d\'équipe faible'),
        ('high_stress_level', 'Niveau de stress élevé'),
        ('low_participation', 'Faible participation'),
        ('significant_change', 'Changement significatif'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relations
    collaborator = models.ForeignKey(Collaborator, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    
    # Informations de l'alerte
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES, verbose_name="Type d'alerte")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium', verbose_name="Sévérité")
    title = models.CharField(max_length=255, verbose_name="Titre")
    message = models.TextField(verbose_name="Message")
    
    # Métadonnées
    is_resolved = models.BooleanField(default=False, verbose_name="Résolu")
    resolved_by = models.ForeignKey(Collaborator, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Résolu le")
    resolution_notes = models.TextField(blank=True, verbose_name="Notes de résolution")
    
    # Données contextuelles
    trigger_data = models.JSONField(default=dict, verbose_name="Données déclencheur")
    notification_sent = models.BooleanField(default=False, verbose_name="Notification envoyée")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_type', 'is_resolved']),
            models.Index(fields=['severity', 'created_at']),
        ]
    
    def resolve(self, resolved_by, notes=""):
        """Marquer l'alerte comme résolue"""
        self.is_resolved = True
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()
    
    def __str__(self):
        return f"{self.title} - {self.get_severity_display()} - {self.created_at.strftime('%d/%m/%Y')}"