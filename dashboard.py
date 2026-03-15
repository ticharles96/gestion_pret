from jet.dashboard import modules
from jet.dashboard.dashboard import Dashboard
from societe.models import Tiers
from parametres.models import Currency

class CustomIndexDashboard(Dashboard):
    columns = 3

    def init_with_context(self, context):
        # 1. Bloc de statistiques textuelles
        self.children.append(modules.LinkList(
            'Statistiques ProjectBank',
            children=[
                {
                    'title': f'Nombre total de Tiers : {Tiers.objects.count()}',
                    'url': '/admin/societe/tiers/',
                },
                {
                    'title': f'Devises enregistrées : {Currency.objects.count()}',
                    'url': '/admin/parametres/currency/',
                },
            ],
            column=0,
            order=0
        ))

        # 2. Bloc des dernières actions (très utile pour l'audit)
        self.children.append(modules.RecentActions(
            'Dernières modifications',
            limit=5,
            column=1,
            order=0
        ))

        # 3. Liste des applications pour ne pas perdre la navigation
        self.children.append(modules.AppList(
            'Navigation Rapide',
            column=2,
            order=0
        ))