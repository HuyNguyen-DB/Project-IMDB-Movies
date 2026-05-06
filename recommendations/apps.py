from django.apps import AppConfig


class RecommendationsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'recommendations'
    verbose_name = 'Quản lý Movie Webapp'

class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        import recommendations.accounts.signals