from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Employe, Company


class EmployeResource(resources.ModelResource):
    # Extraction des données du Tiers (Identity)
    nom = fields.Field(attribute='tiers__nom', column_name='Nom')
    prenom = fields.Field(attribute='tiers__prenoms', column_name='Prénom')
    code_tiers = fields.Field(attribute='tiers__code', column_name='Code Tiers')


    # Champ calculé pour le salaire + devise
    salaire_complet = fields.Field(column_name='Salaire ')
    date_embauche = fields.Field(column_name='Date embauche ')
    est_approbateur= fields.Field(column_name='Est approbateur')

    class Meta:
        model = Employe
        # On définit les colonnes exactes pour le fichier Excel
        fields = ('code_tiers', 'nom', 'prenom', 'date_embauche', 'salaire_complet', 'est_approbateur')
        export_order = ('code_tiers', 'nom', 'prenom', 'date_embauche', 'salaire_complet', 'est_approbateur')

    def dehydrate_salaire_complet(self, employe):
        """
        Cette méthode prépare la donnée 'salaire_complet' pour chaque ligne Excel.
        """
        company = Company.objects.first()
        # On récupère la représentation texte de la monnaie
        devise = str(company.currency) if company and company.currency else ""

        return f"{employe.salaire_base} {devise}"
