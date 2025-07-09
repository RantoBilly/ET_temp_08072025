from django.db import models
from django.db.models import Avg, Count, Sum
from django.db.models.functions import ExtractWeek
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime
import uuid

class EmotionTrendMixin:
    """Mixin pour calculer les tendances émotionnelles"""

    def _calculate_base_emotion_stats(self, daily_emotions):
        """
        Calcule les statistiques de base pour un QuerySet d'émotions
        """
        stats = {
            'total_emotions': daily_emotions.count(),
            'morning_emotions': daily_emotions.filter(half_day=False).count(),
            'evening_emotions': daily_emotions.filter(half_day=True).count(),
            'participation_rate': 0,
            'emotion_distribution': {},
            'average_emotion_degree': 0,
            'emotion_trends': {
                'morning': {},
                'evening': {}
            }
        }

        # Distribution des émotions
        emotion_counts = daily_emotions.values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        )
        for emotion in emotion_counts:
            stats['emotion_distribution'][emotion['emotion_type__emotion_type']] = emotion['count']

        # Moyenne des degrés d'émotion
        avg_degree = daily_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg']
        stats['average_emotion_degree'] = round(avg_degree if avg_degree else 0, 2)

        # Tendances par période (matin/soir)
        for period, half_day in [('morning', False), ('evening', True)]:
            period_emotions = daily_emotions.filter(half_day=half_day)
            emotion_trend = period_emotions.values('emotion_type__emotion_type').annotate(
                count=Count('emotion_type__emotion_type')
            )
            
            for emotion in emotion_trend:
                stats['emotion_trends'][period][emotion['emotion_type__emotion_type']] = emotion['count']
        
        return stats

    def _get_week_date_range(self):
        """Retourne le début et la fin de la semaine en cours"""
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=6)
        return start_of_week, end_of_week

    def _calculate_weekly_base_stats(self, weekly_emotions):
        """
        Calcule les statistiques de base pour la semaine
        """
        stats = {
            'total_emotions': weekly_emotions.count(),
            'daily_breakdown': {},
            'emotion_distribution': {},
            'average_emotion_degree': 0,
            'participation_rate': 0,
            'daily_trends': {},
            'emotion_evolution': []
        }
        
        # Distribution par jour
        start_of_week, end_of_week = self._get_week_date_range()
        current_date = start_of_week
        
        while current_date <= end_of_week:
            day_emotions = weekly_emotions.filter(date=current_date)
            
            stats['daily_breakdown'][current_date.strftime('%Y-%m-%d')] = {
                'count': day_emotions.count(),
                'average_degree': day_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg'] or 0
            }
            
            # Tendances par jour
            day_emotion_counts = day_emotions.values('emotion_type__emotion_type').annotate(
                count=Count('emotion_type__emotion_type')
            )
            
            stats['daily_trends'][current_date.strftime('%Y-%m-%d')] = {
                emotion['emotion_type__emotion_type']: emotion['count']
                for emotion in day_emotion_counts
            }
            
            current_date += timezone.timedelta(days=1)
        
        # Distribution globale des émotions
        emotion_counts = weekly_emotions.values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        )
        stats['emotion_distribution'] = {
            emotion['emotion_type__emotion_type']: emotion['count']
            for emotion in emotion_counts
        }
        
        # Moyenne globale
        avg_degree = weekly_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg']
        stats['average_emotion_degree'] = round(avg_degree if avg_degree else 0, 2)
        
        # Évolution des émotions
        daily_averages = weekly_emotions.values('date').annotate(
            avg_degree=Avg('emotion_degree')
        ).order_by('date')
        
        stats['emotion_evolution'] = [
            {
                'date': entry['date'].strftime('%Y-%m-%d'),
                'average_degree': round(entry['avg_degree'] if entry['avg_degree'] else 0, 2)
            }
            for entry in daily_averages
        ]
        
        return stats

    def _get_month_date_range(self):
        """Retourne le début et la fin du mois en cours"""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        next_month = start_of_month + timezone.timedelta(days=32)
        end_of_month = next_month.replace(day=1) - timezone.timedelta(days=1)
        return start_of_month, end_of_month

    def _calculate_monthly_base_stats(self, monthly_emotions):
        """
        Calcule les statistiques de base pour le mois
        """
        stats = {
            'total_emotions': monthly_emotions.count(),
            'weekly_breakdown': {},
            'emotion_distribution': {},
            'average_emotion_degree': 0,
            'participation_rate': 0,
            'weekly_trends': {},
            'emotion_evolution': [],
            'peak_days': {
                'highest': None,
                'lowest': None
            }
        }
        
        # Distribution par semaine
        weekly_stats = monthly_emotions.annotate(
            week=ExtractWeek('date')
        ).values('week').annotate(
            count=Count('id'),
            avg_degree=Avg('emotion_degree')
        ).order_by('week')
        
        for week_stat in weekly_stats:
            stats['weekly_breakdown'][f"Week-{week_stat['week']}"] = {
                'count': week_stat['count'],
                'average_degree': round(week_stat['avg_degree'] if week_stat['avg_degree'] else 0, 2)
            }
        
        # Distribution globale des émotions
        emotion_counts = monthly_emotions.values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        )
        stats['emotion_distribution'] = {
            emotion['emotion_type__emotion_type']: emotion['count']
            for emotion in emotion_counts
        }
        
        # Moyenne globale
        avg_degree = monthly_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg']
        stats['average_emotion_degree'] = round(avg_degree if avg_degree else 0, 2)
        
        # Évolution quotidienne des émotions
        daily_stats = monthly_emotions.values('date').annotate(
            count=Count('id'),
            avg_degree=Avg('emotion_degree')
        ).order_by('date')
        
        stats['emotion_evolution'] = [
            {
                'date': entry['date'].strftime('%Y-%m-%d'),
                'count': entry['count'],
                'average_degree': round(entry['avg_degree'] if entry['avg_degree'] else 0, 2)
            }
            for entry in daily_stats
        ]
        
        # Identifier les pics
        if daily_stats:
            highest = max(daily_stats, key=lambda x: x['avg_degree'] or 0)
            lowest = min(daily_stats, key=lambda x: x['avg_degree'] or 0)
            
            stats['peak_days'] = {
                'highest': {
                    'date': highest['date'].strftime('%Y-%m-%d'),
                    'degree': round(highest['avg_degree'] if highest['avg_degree'] else 0, 2)
                },
                'lowest': {
                    'date': lowest['date'].strftime('%Y-%m-%d'),
                    'degree': round(lowest['avg_degree'] if lowest['avg_degree'] else 0, 2)
                }
            }
        
        return stats


class Company(models.Model, EmotionTrendMixin):
    """Modèle pour les entreprises"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Nom de l'entreprise")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ['name']

    def calculate_daily_emotion_trend(self):
        """
        Calcule les tendances émotionnelles des collaborateurs de l'entreprise pour la journée
        """
        today = timezone.now().date()
        
        # Récupérer toutes les émotions des collaborateurs de l'entreprise pour aujourd'hui
        daily_emotions = Emotion.objects.filter(
            collaborator__company=self,
            date=today
        )

        stats = self._calculate_base_emotion_stats(daily_emotions)

        # Calculer le taux de participation pour l'entreprise
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            stats['participation_rate'] = (daily_emotions.values('collaborator').distinct().count() / total_collaborators) * 100

        # Ajouter des statistiques spécifiques à l'entreprise
        stats['service_breakdown'] = self._calculate_service_breakdown(daily_emotions)
        stats['cluster_breakdown'] = self._calculate_cluster_breakdown(daily_emotions)

        return stats

    def _calculate_service_breakdown(self, daily_emotions):
        """Calcule la répartition des émotions par service"""
        return dict(daily_emotions.values('collaborator__service__service_name')
                   .annotate(count=Count('id'))
                   .values_list('collaborator__service__service_name', 'count'))

    def _calculate_cluster_breakdown(self, daily_emotions):
        """Calcule la répartition des émotions par cluster"""
        return dict(daily_emotions.values('collaborator__cluster__name')
                   .annotate(count=Count('id'))
                   .values_list('collaborator__cluster__name', 'count'))

    def calculate_weekly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles hebdomadaires de l'entreprise
        """
        start_of_week, end_of_week = self._get_week_date_range()
        
        weekly_emotions = Emotion.objects.filter(
            collaborator__company=self,
            date__range=[start_of_week, end_of_week]
        )
        
        stats = self._calculate_weekly_base_stats(weekly_emotions)
        
        # Calculer le taux de participation hebdomadaire
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = weekly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques à l'entreprise
        stats['service_breakdown'] = self._calculate_weekly_service_breakdown(weekly_emotions)
        stats['cluster_breakdown'] = self._calculate_weekly_cluster_breakdown(weekly_emotions)
        
        return stats

    def _calculate_weekly_service_breakdown(self, weekly_emotions):
        """Répartition hebdomadaire par service"""
        return dict(
            weekly_emotions.values('collaborator__service__service_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__service__service_name', 'count')
        )
    
    def _calculate_weekly_cluster_breakdown(self, weekly_emotions):
        """Répartition hebdomadaire par cluster"""
        return dict(
            weekly_emotions.values('collaborator__cluster__name')
            .annotate(count=Count('id'))
            .values_list('collaborator__cluster__name', 'count')
        )

    def calculate_monthly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles mensuelles de l'entreprise
        """
        start_of_month, end_of_month = self._get_month_date_range()
        
        monthly_emotions = Emotion.objects.filter(
            collaborator__company=self,
            date__range=[start_of_month, end_of_month]
        )
        
        stats = self._calculate_monthly_base_stats(monthly_emotions)
        
        # Calculer le taux de participation mensuel
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = monthly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques à l'entreprise
        stats['service_breakdown'] = self._calculate_monthly_service_breakdown(monthly_emotions)
        stats['cluster_breakdown'] = self._calculate_monthly_cluster_breakdown(monthly_emotions)
        
        # Ajouter l'analyse des tendances
        stats['trend_analysis'] = self._analyze_monthly_trends(monthly_emotions)
        
        return stats

    def _calculate_monthly_service_breakdown(self, monthly_emotions):
        """Répartition mensuelle par service"""
        return dict(
            monthly_emotions.values('collaborator__service__service_name')
            .annotate(
                count=Count('id'),
                avg_degree=Avg('emotion_degree')
            )
            .values_list(
                'collaborator__service__service_name',
                'count'
            )
        )

    def _calculate_monthly_cluster_breakdown(self, monthly_emotions):
        """Répartition mensuelle par cluster"""
        return dict(
            monthly_emotions.values('collaborator__cluster__name')
            .annotate(
                count=Count('id'),
                avg_degree=Avg('emotion_degree')
            )
            .values_list(
                'collaborator__cluster__name',
                'count'
            )
        )

    def _analyze_monthly_trends(self, monthly_emotions):
        """Analyse des tendances mensuelles"""
        return {
            'dominant_emotion': monthly_emotions.values('emotion_type__emotion_type')
                .annotate(count=Count('id'))
                .order_by('-count')
                .first(),
            'emotion_progression': list(
                monthly_emotions.values('date')
                .annotate(avg_degree=Avg('emotion_degree'))
                .order_by('date')
                .values('date', 'avg_degree')
            )
        }
    
    def __str__(self):
        return self.name


class Cluster(models.Model, EmotionTrendMixin):
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

    def calculate_daily_emotion_trend(self):
        """
        Calcule les tendances émotionnelles des collaborateurs du cluster pour la journée
        """
        today = timezone.now().date()
        
        # Récupérer toutes les émotions des collaborateurs du cluster pour aujourd'hui
        daily_emotions = Emotion.objects.filter(
            collaborator__cluster=self,
            date=today
        )
        
        stats = self._calculate_base_emotion_stats(daily_emotions)
        
        # Calculer le taux de participation pour le cluster
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            stats['participation_rate'] = (daily_emotions.values('collaborator').distinct().count() / total_collaborators) * 100
        
        # Ajouter des statistiques spécifiques au cluster
        stats['service_breakdown'] = self._calculate_service_breakdown(daily_emotions)
        
        return stats
    
    def _calculate_service_breakdown(self, daily_emotions):
        """Calcule la répartition des émotions par service dans le cluster"""
        return dict(daily_emotions.values('collaborator__service__service_name')
                   .annotate(count=Count('id'))
                   .values_list('collaborator__service__service_name', 'count'))

    def calculate_weekly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles hebdomadaires du cluster
        """
        start_of_week, end_of_week = self._get_week_date_range()
        
        weekly_emotions = Emotion.objects.filter(
            collaborator__cluster=self,
            date__range=[start_of_week, end_of_week]
        )
        
        stats = self._calculate_weekly_base_stats(weekly_emotions)
        
        # Calculer le taux de participation hebdomadaire
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = weekly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques au cluster
        stats['service_breakdown'] = self._calculate_weekly_service_breakdown(weekly_emotions)

        return stats


    def _calculate_weekly_service_breakdown(self, weekly_emotions):
        """Répartition hebdomadaire par service dans le cluster"""
        return dict(
            weekly_emotions.values('collaborator__service__service_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__service__service_name', 'count')
        )

    def calculate_monthly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles mensuelles du cluster
        """
        start_of_month, end_of_month = self._get_month_date_range()
        
        monthly_emotions = Emotion.objects.filter(
            collaborator__cluster=self,
            date__range=[start_of_month, end_of_month]
        )
        
        stats = self._calculate_monthly_base_stats(monthly_emotions)
        
        # Calculer le taux de participation mensuel
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = monthly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques au cluster
        stats['service_breakdown'] = self._calculate_monthly_service_breakdown(monthly_emotions)
        stats['team_distribution'] = self._calculate_monthly_team_distribution(monthly_emotions)
        
        return stats

    def _calculate_monthly_service_breakdown(self, monthly_emotions):
        """Répartition mensuelle par service"""
        return dict(
            monthly_emotions.values('collaborator__service__service_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__service__service_name', 'count')
        )
    
    def _calculate_monthly_team_distribution(self, monthly_emotions):
        """Distribution mensuelle par équipe"""
        return dict(
            monthly_emotions.values('collaborator__team__team_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__team__team_name', 'count')
        )
        
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"


class Service(models.Model, EmotionTrendMixin):
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

    def calculate_daily_emotion_trend(self):
        """
        Calcule les tendances émotionnelles des collaborateurs du service pour la journée
        Retourne un dictionnaire contenant les statistiques émotionnelles
        """
        today = timezone.now().date()

        # Récupérer toutes les émotions des collaborateurs du service pour aujourd'hui
        daily_emotions = Emotion.objects.filter(
        collaborator__service=self,
        date=today
        )

        # Statistiques de base
        stats = {
            'total_emotions': daily_emotions.count(),
            'morning_emotions': daily_emotions.filter(half_day=False).count(),
            'evening_emotions': daily_emotions.filter(half_day=True).count(),
            'participation_rate': 0,
            'emotion_distribution': {},
            'average_emotion_degree': 0,
            'emotion_trends': {
                'morning': {},
                'evening': {}
            }
        }

        # Calculer le taux de participation
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            stats['participation_rate'] = (daily_emotions.values('collaborator').distinct().count() / total_collaborators) * 100
        
        # Distribution des émotions
        emotion_counts = daily_emotions.values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        )   
        for emotion in emotion_counts:
            stats['emotion_distribution'][emotion['emotion_type__emotion_type']] = emotion['count']

        # Moyenne des degrés d'émotion
        avg_degree = daily_emotions.aggregate(Avg('emotion_degree'))['emotion_degree__avg']
        stats['average_emotion_degree'] = round(avg_degree if avg_degree else 0, 2)

        # Tendances par période (matin/soir)
        for period, half_day in [('morning', False), ('evening', True)]:
            period_emotions = daily_emotions.filter(half_day=half_day)
            emotion_trend = period_emotions.values('emotion_type__emotion_type').annotate(
                count=Count('emotion_type__emotion_type')
            )

            for emotion in emotion_trend:
                stats['emotion_trends'][period][emotion['emotion_type__emotion_type']] = emotion['count']

        return stats

    def get_dominant_emotion(self):
        """
        Retourne l'émotion dominante du service pour la journée
        """
        today = timezone.now().date()

        dominant_emotion = Emotion.objects.filter(
            collaborator__service=self,
            date=today
        ).values('emotion_type__emotion_type').annotate(
            count=Count('emotion_type__emotion_type')
        ).order_by('-count').first()

        return dominant_emotion['emotion_type__emotion_type'] if dominant_emotion else None

    def get_emotion_alerts(self):
        """
        Retourne les alertes émotionnelles du service pour la journée
        """

        alerts = []

        today = timezone.now().date()
        stats = self.calculate_daily_emotion_trend()

        # Alerte si le taux de participation est faible (<50%)
        if stats['participation_rate'] < 50:
            alerts.append({
                'type': 'low_participation',
                'message': f"Faible taux de participation ({stats['participation_rate']}%) dans le service {self.service_name}"
            })

        # Alerte si la moyenne des émotions est négative
        if stats['average_emotion_degree'] < 0:
            alerts.append({
                'type': 'negative_emotions',
                'message': f"Tendance émotionnelle négative dans le service {self.service_name}"
            })

        return alerts

    def calculate_weekly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles hebdomadaires du service
        """
        start_of_week, end_of_week = self._get_week_date_range()
        
        weekly_emotions = Emotion.objects.filter(
            collaborator__service=self,
            date__range=[start_of_week, end_of_week]
        )
        
        stats = self._calculate_weekly_base_stats(weekly_emotions)
        
        # Calculer le taux de participation hebdomadaire
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = weekly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques au service
        stats['team_breakdown'] = self._calculate_weekly_team_breakdown(weekly_emotions)
        
        return stats

    def _calculate_weekly_team_breakdown(self, weekly_emotions):
        """Répartition hebdomadaire par équipe"""
        return dict(
            weekly_emotions.values('collaborator__team__team_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__team__team_name', 'count')
        )

    def calculate_monthly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles mensuelles du service
        """
        start_of_month, end_of_month = self._get_month_date_range()
        
        monthly_emotions = Emotion.objects.filter(
            collaborator__service=self,
            date__range=[start_of_month, end_of_month]
        )
        
        stats = self._calculate_monthly_base_stats(monthly_emotions)
        
        # Calculer le taux de participation mensuel
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = monthly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques au service
        stats['team_breakdown'] = self._calculate_monthly_team_breakdown(monthly_emotions)
        stats['role_distribution'] = self._calculate_monthly_role_distribution(monthly_emotions)
        
        return stats

    def _calculate_monthly_team_breakdown(self, monthly_emotions):
        """Répartition mensuelle par équipe"""
        return dict(
            monthly_emotions.values('collaborator__team__team_name')
            .annotate(count=Count('id'))
            .values_list('collaborator__team__team_name', 'count')
        )
    
    def _calculate_monthly_role_distribution(self, monthly_emotions):
        """Distribution mensuelle par rôle"""
        return dict(
            monthly_emotions.values('collaborator__role')
            .annotate(count=Count('id'))
            .values_list('collaborator__role', 'count')
        )
    
    def __str__(self):
        return self.service_name


class Team(models.Model, EmotionTrendMixin):
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

    def calculate_daily_emotion_trend(self):
        """
        Calcule les tendances émotionnelles des collaborateurs de l'équipe pour la journée
        """
        today = timezone.now().date()
        
        # Récupérer toutes les émotions des collaborateurs de l'équipe pour aujourd'hui
        daily_emotions = Emotion.objects.filter(
            collaborator__team=self,
            date=today
        )
        
        stats = self._calculate_base_emotion_stats(daily_emotions)
        
        # Calculer le taux de participation pour l'équipe
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            stats['participation_rate'] = (daily_emotions.values('collaborator').distinct().count() / total_collaborators) * 100
        
        # Ajouter des statistiques spécifiques à l'équipe
        stats['role_breakdown'] = self._calculate_role_breakdown(daily_emotions)
        
        return stats
    
    def _calculate_role_breakdown(self, daily_emotions):
        """Calcule la répartition des émotions par rôle dans l'équipe"""
        return dict(daily_emotions.values('collaborator__role')
                   .annotate(count=Count('id'))
                   .values_list('collaborator__role', 'count'))

    def calculate_weekly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles hebdomadaires de l'équipe
        """
        start_of_week, end_of_week = self._get_week_date_range()
        
        weekly_emotions = Emotion.objects.filter(
            collaborator__team=self,
            date__range=[start_of_week, end_of_week]
        )
        
        stats = self._calculate_weekly_base_stats(weekly_emotions)
        
        # Calculer le taux de participation hebdomadaire
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = weekly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques à l'équipe
        stats['role_breakdown'] = self._calculate_weekly_role_breakdown(weekly_emotions)
        
        return stats

    def _calculate_weekly_role_breakdown(self, weekly_emotions):
        """Répartition hebdomadaire par rôle"""
        return dict(
            weekly_emotions.values('collaborator__role')
            .annotate(count=Count('id'))
            .values_list('collaborator__role', 'count')
        )

    def calculate_monthly_emotion_trend(self):
        """
        Calcule les tendances émotionnelles mensuelles de l'équipe
        """
        start_of_month, end_of_month = self._get_month_date_range()
        
        monthly_emotions = Emotion.objects.filter(
            collaborator__team=self,
            date__range=[start_of_month, end_of_month]
        )
        
        stats = self._calculate_monthly_base_stats(monthly_emotions)
        
        # Calculer le taux de participation mensuel
        total_collaborators = self.collaborators.filter(is_active=True).count()
        if total_collaborators > 0:
            participants = monthly_emotions.values('collaborator').distinct().count()
            stats['participation_rate'] = (participants / total_collaborators) * 100
        
        # Ajouter les breakdowns spécifiques à l'équipe
        stats['role_breakdown'] = self._calculate_monthly_role_breakdown(monthly_emotions)
        stats['member_participation'] = self._calculate_member_participation(monthly_emotions)
        
        return stats

    def _calculate_monthly_role_breakdown(self, monthly_emotions):
        """Répartition mensuelle par rôle"""
        return dict(
            monthly_emotions.values('collaborator__role')
            .annotate(count=Count('id'))
            .values_list('collaborator__role', 'count')
        )
    
    def _calculate_member_participation(self, monthly_emotions):
        """Calcul de la participation par membre"""
        return dict(
            monthly_emotions.values('collaborator__full_name')
            .annotate(
                emotion_count=Count('id'),
                avg_emotion=Avg('emotion_degree')
            )
            .values(
                'collaborator__full_name',
                'emotion_count',
                'avg_emotion'
            )
        )
    
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
            today_evening_emotion = Emotion.objects.filter(
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

        # Déterminer emotion_this_month en fonction de emotion_degree_this_month
        if self.emotion_degree_this_month is not None:
            if self.emotion_degree_this_month <= -5:
                self.emotion_this_month = "Angry"
            elif self.emotion_degree_this_month <= -2:
                self.emotion_this_month = "Anxious"
            elif self.emotion_degree_this_month <= -1:
                self.emotion_this_month = "Sad"
            elif self.emotion_degree_this_month == 0:
                self.emotion_this_month = "Neutral"
            elif self.emotion_degree_this_month <= 5:
                self.emotion_this_month = "Happy"
            else:
                self.emotion_this_month = "Excited"
        else:
            self.emotion_this_month = None

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
        self.degree = emotion_degree_mapping.get(self.emotion, 0)  # 0 par défaut si non trouvé

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

