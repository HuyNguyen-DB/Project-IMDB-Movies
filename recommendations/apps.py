from django.apps import AppConfig


class RecommendationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommendations'

class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        import recommendations.accounts.signals