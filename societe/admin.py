
from django.utils.safestring import mark_safe
from django.forms import SelectDateWidget
import datetime
from django.contrib import admin
from django.utils import timezone
from django.contrib.auth.models import User  # Correction : import depuis auth.models
from django.utils.html import format_html
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

# Importation de vos modèles
from .models import Depense
from societe.models import Employe
from import_export.admin import ExportMixin
from phonenumber_field.widgets import PhoneNumberPrefixWidget # <-- Le bon nom est ici
from django.utils.html import format_html
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect

from .models import Company, Phone, CompanyAddress, CompanyBank, Tiers, Contact, TiersAdresse, IdentityDocument, \
    Employe, Depense
from .resources import EmployeResource
from .views import generate_company_info_pdf  # On importe la vue créée précédemment
from django import forms # Importez forms
from .models import CompanyAddress
from django.db import models


# Register your models here.
class IdentityDocumentInline(admin.StackedInline):
    model = IdentityDocument
    can_delete = False  # Empêche la suppression accidentelle du dossier doc
    verbose_name = "Dossier d'Identification"
    verbose_name_plural = "Documents & Médias"
    extra = 1  # Affiche un formulaire vide si aucun document n'existe
    max_num = 1  # Limite à un seul dossier par Tiers
    min_num = 1  # <--- FORCE la présence d'au moins un formulaire

    # Empêche de laisser le type de pièce vide
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.validate_min = True  # Force la validation du minimum
        return formset

    # Organisation visuelle des champs
    fieldsets = (
        (None, {
            'fields': (
                'photo',
                'type_piece',
                'numero_document',
                ('piece_identite_recto', 'piece_identite_verso'),  # Affiche côte à côte
                'signature'
            )
        }),
    )

    # Injection du JavaScript pour masquer le Verso si "Passeport"
    class Media:
        js = ('admin/js/hide_verso_inline.js',)
#pour gerer adresse Tiers
class AdresseInline(admin.TabularInline):
    model = TiersAdresse
    extra = 0  # Nombre de lignes vides à afficher par défaut
    min_num = 1
    can_delete = True
    fields = ('est_principale', 'type_adresse', 'departement', 'ville','rue')

@admin.register(TiersAdresse)
class AdresseAdmin(admin.ModelAdmin):
    list_display = ('departement', 'ville','rue', 'type_adresse', 'tiers', 'est_principale')
    list_filter = ('departement','ville', 'type_adresse', 'est_principale')
    search_fields = ('rue', 'ville', 'tiers__nom')
    autocomplete_fields = ['tiers']

#pour gerer contact tiers
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste
    list_display = ('valeur', 'type_contact', 'tiers', 'est_principal', 'icone_visuelle')

    # Filtres sur le côté droit
    list_filter = ('type_contact', 'est_principal', 'tiers')

    # Barre de recherche (recherche par valeur ou par nom du tiers)
    search_fields = ('valeur', 'tiers__nom')

    # Configuration des champs lors de l'édition
    fields = ('tiers', 'type_contact', 'valeur', 'est_principal')

    # Pour rendre l'interface plus rapide si vous avez des milliers de Tiers
    autocomplete_fields = ['tiers']

    class Media:
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',)
        }

#pour moyens de contact
class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0  # Nombre de lignes vides à afficher par défaut
    min_num = 1
    can_delete = True
    readonly_fields = ('icone_visuelle',)
    fields = ('est_principal', 'type_contact', 'icone_visuelle', 'valeur')

    # On injecte un petit JS pour changer le type d'input
    class Media:
        # Importation des icônes
        css = {
            'all': ('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',)
        }
        js = ('js/contact_admin.js',)


#class pour gerer Tiers
@admin.register(Tiers)
class TiersAdmin(admin.ModelAdmin):
    inlines = [ContactInline, AdresseInline, IdentityDocumentInline]
    # --- Configuration de la Liste ---
    list_display = ("photo_cercle", "code", "nom", "prenoms", "genre","religion","created_by", "view_pdf")
    list_per_page = 50
    list_display_links = ("photo_cercle", "code", "nom")
    list_filter = ('genre', 'religion',)
    search_fields = ('code', 'nom', 'prenoms', )

    # --- Champs en lecture seule ---
    # On ajoute 'print_button' pour l'avoir dans le formulaire

    # Calcul des années autorisées (ex: de 1920 jusqu'à il y a 16 ans)
    YEAR_MAX = datetime.date.today().year - 16
    YEARS = [year for year in range(1920, YEAR_MAX + 1)]

    # pour changer format de la date
    CURRENT_YEAR = datetime.date.today().year
    YEARS = [year for year in range(1920, CURRENT_YEAR + 1)]

    formfield_overrides = {
        models.DateField: {
            'widget': SelectDateWidget(years=YEARS)
        },
    }

    # On n'affiche PAS le champ dans le formulaire de saisie
    exclude = ('created_by',)

    def photo_tag(self):
        try:
            # On cherche la photo dans le modèle lié via 'identity_docs'
            if self.identity_docs and self.identity_docs.photo:
                return mark_safe(
                    f'<img src="{self.identity_docs.photo.url}" width="40" height="40" style="border-radius: 50%; object-fit: cover;" />')
        except:
            # Si le document d'identité n'est pas encore créé pour ce tiers
            pass
        return mark_safe('<span style="font-size: 20px; color: #ccc;">👤</span>')

    photo_tag.short_description = 'Photo'

    def afficher_contacts_rapides(self, obj):
        contacts = obj.moyens_contact.all()
        if not contacts: return "Aucun"

        # Test : on affiche la valeur en texte brut au lieu de l'icône
        return mark_safe(", ".join([f'<a href="#">{c.valeur}</a>' for c in contacts]))

    def save_model(self, request, obj, form, change):
        # Si l'objet n'a pas encore de créateur (nouvel enregistrement)
        if not obj.created_by:
            obj.created_by = request.user

        # On sauvegarde normalement
        super().save_model(request, obj, form, change)

        # Organisation par sections
        fieldsets = (
            ('Informations Personnelles', {
                'fields': ('nom', 'prenoms', 'date_naissance', 'genre', 'statut_matrimonial', 'religion',
                           'niveau_etude', 'nombre_enfants')
            }),
            ('Contact & Système', {
                'fields': ('email', 'code')
            }),

        )

        readonly_fields = ('code',)
    # --- 1. Bouton PDF dans la liste (Colonne) ---
    def view_pdf(self, obj):
        url = reverse('profil_pdf', kwargs={'pk': obj.pk})
        return format_html(
            '<a class="button" href="{}" target="_blank" style="padding: 2px 10px;">PDF</a>',
            url
        )
    view_pdf.short_description = "Fiche"

    # --- 2. Bouton PDF dans le détail (Fieldset) ---
    def print_button(self, obj):
        if obj.pk:
            url = reverse('profil_pdf', kwargs={'pk': obj.pk})
            return format_html(
                '<a href="{}" target="_blank" style="display: inline-block; padding: 8px 15px; background: #447e9b; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">🖨️ Imprimer la fiche complète</a>',
                url
            )
        return "Disponible après enregistrement"
    print_button.short_description = "Impression"

    def photo_cercle(self, obj):
        identity = getattr(obj, 'identity_docs', None)

        if identity and identity.photo:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; border: 1px solid #ddd;" />',
                identity.photo.url
            )

        # Pour une chaîne statique sans variables {}, on utilise mark_safe
        return mark_safe(
            '<div style="width: 40px; height: 40px; border-radius: 50%; background-color: #eee; '
            'display: flex; align-items: center; justify-content: center; color: #999; font-size: 10px;">'
            'N/A</div>'
        )

    photo_cercle.short_description = 'Photo'
    class Media:
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.19/js/intlTelInput.min.js',
            'admin/js/tiers_admin.js',
        )
# class pour gerer l'entreprise
class CompanyBankInline(admin.StackedInline):
    model = CompanyBank
    extra = 0  # Nombre de lignes vides à afficher par défaut
    min_num = 1
    can_delete = True

    # On peut aussi ajuster la largeur des colonnes ici si besoin

class CompanyAddressInline(admin.StackedInline): # Stacked est mieux pour les TextFields (plus d'espace)
    model = CompanyAddress
    extra = 0  # Nombre de lignes vides à afficher par défaut
    min_num = 1
    can_delete = True
    # On définit le Widget ici pour agrandir l'espace de saisie
    formfield_overrides = {
        models.CharField: {
            'widget': forms.TextInput(attrs={'style': 'width: 600px; padding: 10px;'})
        },
    }


# Configuration de l'affichage en ligne
class CompanyPhoneInline(admin.TabularInline):
    model = Phone
    extra = 0  # Nombre de lignes vides à afficher par défaut
    min_num = 1 # Obliger à saisir au moins un numéro
    can_delete = True
    show_change_link = True


#class pour enregistrer la compagnie dans l'admin
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    # Les champs qui seront affichés en colonnes dans la liste
    list_display = ('download_pdf_link','show_logo', 'name', 'display_currency', 'display_capital', 'display_interest', 'display_frais_dossier_pct','display_penalite','display_interest_bric_a_brac')

    change_form_template = "admin/company_change_form.html"
    inlines = [CompanyPhoneInline, CompanyAddressInline, CompanyBankInline]  # On ajoute les téléphones ici
    # Lien pour la liste principale
    def download_pdf_link(self, obj):
        # On construit l'URL directement.
        # Structure : /admin/NOM_APP/NOM_MODELE/ID/pdf/
        return format_html(
            '<a class="button" style="background-color: #79aec8; color: white;" href="{}/pdf/">PDF</a>',
            obj.pk
        )

    download_pdf_link.short_description = "Rapport PDF"

    # Définition de l'URL personnalisée
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/pdf/',  # On utilise <path:object_id> pour capturer l'ID sans conflit
                self.admin_site.admin_view(generate_company_info_pdf),
                name='company-pdf-view',  # Nom interne
            ),
        ]
        return custom_urls + urls

    def get_urls(self):
        # On récupère les URLs par défaut
        urls = super().get_urls()
        # On définit notre URL personnalisée
        custom_urls = [
            path(
                '<int:company_id>/pdf/',
                self.admin_site.admin_view(generate_company_info_pdf),
                name='company-pdf',  # Ce nom est utilisé par reverse() ci-dessus
            ),
        ]
        # IMPORTANT : On place les custom_urls AVANT les urls par défaut
        return custom_urls + urls


    def display_currency(self, obj):
        return obj.currency

    display_currency.short_description = "Monnaie"

    def display_capital(self, obj):
        return f"{obj.capital} {obj.currency}"

    display_capital.short_description = "Capital"


    display_capital.short_description = "Capital"

    def display_interest(self, obj):
        return f"{obj.default_interest_rate} %"
    display_interest.short_description = "Taux prêt"

    def display_frais_dossier_pct(self, obj):
        return f"{obj.frais_dossier_pct} %"
    display_frais_dossier_pct.short_description = "Frais de dossiers"

    def display_interest_bric_a_brac(self, obj):
        return f"{obj.interet_maison_daffaire}%"
    display_interest_bric_a_brac.short_description = "Taux Maison d'affaires"

    def display_penalite(self, obj):
        return f"{obj.late_fee_value}{obj.currency}"

    display_penalite.short_description = "Penalite"

    # Rendre le nom cliquable pour modifier la fiche
    list_display_links = ('show_logo','name',)

    # Ajouter une barre de recherche
    search_fields = ('name', 'tax_id', 'email')

    # Utilisation du widget pour les drapeaux dans le formulaire de modification
    formfield_overrides = {
        'phone': {'widget': PhoneNumberPrefixWidget},
    }

    # Fonction pour afficher une miniature du logo dans la liste
    def show_logo(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="width: 45px; height: auto; border-radius: 5px;" />', obj.logo.url)
        return "Pas de logo"

    show_logo.short_description = 'Logo'

    # Fonction pour afficher le capital avec sa devise dans la liste
    def capital_with_currency(self, obj):
        return f"{obj.capital:,} {obj.currency}".replace(',', ' ')

    capital_with_currency.short_description = 'Capital Social'
    # On remplace le widget par défaut par celui qui gère les drapeaux
    fformfield_overrides = {
        'phone': {'widget': PhoneNumberPrefixWidget},
    }
    def has_add_permission(self, request):
        # Si une entreprise existe déjà, on ne peut plus en ajouter
        if Company.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Empêcher la suppression accidentelle de l'info de l'entreprise
        return False


#admin pour employer
@admin.register(Employe)
class EmployeAdmin(ExportMixin, admin.ModelAdmin):
    # Utilisation de la ressource d'exportation
    resource_class = EmployeResource

    # 1. AFFICHAGE DE LA LISTE
    list_display = (
        'display_photo',
        'get_nom_complet',
        'get_postes',
        'afficher_salaire',
        'date_embauche',
        'created_at',
        'updated_at',
        'created_by',
        'est_approbateur'
    )

    # 2. FILTRES ET RECHERCHE
    list_filter = ('poste', 'est_approbateur', 'date_embauche')
    search_fields = ('tiers__nom', 'tiers__prenoms', 'tiers__code')
    list_display_links = ['get_nom_complet', 'display_photo']

    # Interface de sélection pour le ManyToMany
    filter_horizontal = ('poste',)

    # 3. CONFIGURATION DES CHAMPS DU FORMULAIRE
    # On ajoute 'created_by' en lecture seule pour qu'il s'affiche sans erreur
    readonly_fields = ('created_by', 'created_at', 'updated_at')

    fields = ('tiers', 'poste', 'salaire_base', 'date_embauche', 'est_approbateur',)
    # 'user' est géré automatiquement par votre modèle, on l'exclut du formulaire
    exclude = ('user',)

    # 4. LOGIQUE DE SAUVEGARDE (Auto-remplissage du créateur)
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Si c'est une création
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # 5. MÉTHODES D'AFFICHAGE PERSONNALISÉES
    def afficher_salaire(self, obj):
        # On utilise une mise en cache simple pour éviter de requêter Company 100 fois
        if not hasattr(self, '_company_cache'):
            self._company_cache = Company.objects.first()

        company = self._company_cache
        devise = str(company.currency) if company and company.currency else ""

        return f"{obj.salaire_base} {devise}"

    afficher_salaire.short_description = 'Salaire'

    def get_postes(self, obj):
        return ", ".join([group.name for group in obj.poste.all()])

    get_postes.short_description = 'Postes Occupés'

    def display_photo(self, obj):
        if obj.tiers:
            return obj.tiers.photo_tag()
        return "-"

    display_photo.short_description = 'Photo'

    def get_nom_complet(self, obj):
        return f"{obj.tiers.nom.upper()} {obj.tiers.prenoms}"

    get_nom_complet.short_description = 'Employé'

    # Optimisation SQL : On récupère les relations liées en une seule fois
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tiers', 'created_by').prefetch_related('poste')

# pour forcer l'utilisateur a changer mot de passe lors de la premiere connection
# On surcharge la vue de l'index de l'admin
admin.site.index_template = "admin/index.html"  # Utilise le template par défaut


# On intercepte la vue principale de l'admin
def restricted_index(request, extra_context=None):
    if request.user.is_authenticated:
        try:
            # On vérifie si l'utilisateur est un employé et doit changer son MDP
            employe = request.user.profil_employe
            if employe.doit_changer_mot_de_passe:
                return redirect(reverse('admin:password_change'))
        except AttributeError:
            # C'est un superadmin ou un user sans profil employé, on laisse passer
            pass

    # Si tout est OK, on affiche l'index normal
    return admin.site.__class__.index(admin.site, request, extra_context)


# On remplace la vue index par la nôtre
admin.site.index = restricted_index

#pour mot de passe oublie dans login
# On injecte la variable company_info dans toutes les pages de l'admin
admin.site.site_header = "Gestion Bancaire" # Optionnel

def get_company_context(request):
    return {'company_info': Company.objects.first()}

# On surcharge la méthode login de l'admin
original_login = admin.site.login

def custom_login(request, extra_context=None):
    if extra_context is None:
        extra_context = {}
    extra_context.update(get_company_context(request))
    return original_login(request, extra_context)

admin.site.login = custom_login

#admin pour les depenses
# --- 1. Ressource pour l'exportation Excel/CSV ---
class DepenseResource(resources.ModelResource):
    employe_responsable = fields.Field(
        column_name='Employé Responsable',
        attribute='employe_responsable',
        widget=ForeignKeyWidget(Employe, 'nom')
    )

    enregistre_par = fields.Field(
        column_name='Enregistré par',
        attribute='enregistre_par',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = Depense
        fields = ('date_depense', 'titre', 'montant', 'employe_responsable', 'description', 'enregistre_par')
        export_order = fields


# --- 2. Configuration de l'interface Admin ---
@admin.register(Depense)
class DepenseAdmin(ImportExportModelAdmin):
    resource_class = DepenseResource

    # Configuration de la liste
    list_display = ('date_depense', 'titre', 'display_montant_devise', 'employe_responsable', 'enregistre_par')
    list_filter = ('date_depense', 'employe_responsable', 'date_creation')
    search_fields = ('titre', 'description')
    readonly_fields = ('date_creation', 'date_modification', 'enregistre_par')

    fieldsets = (
        ('Détails Financiers', {
            'fields': ('titre', 'montant', 'date_depense', 'description')
        }),
        ('Responsabilité', {
            'fields': ('employe_responsable',)
        }),
        ('Audit & Traçabilité', {
            'fields': ('enregistre_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',),
        }),
    )

    # AFFICHAGE DU MONTANT AVEC LA DEVISE DE LA COMPANY
    def display_montant_devise(self, obj):
        devise_texte = ""
        try:
            # 1. On accède à l'objet Currency via la Company
            currency_obj = obj.employe_responsable.company.currency

            if currency_obj:
                # 2. On récupère sa représentation (ex: "USD" ou "$")
                # Si votre modèle Currency a un champ 'code' ou 'symbol',
                # vous pouvez utiliser currency_obj.code ou currency_obj.symbol
                devise_texte = str(currency_obj)
        except AttributeError:
            devise_texte = ""

        montant_formate = "{:,.2f}".format(obj.montant)

        return format_html(
            '<b style="color: #2c3e50;">{} <span style="color: #7f8c8d; font-weight: normal;">{}</span></b>',
            montant_formate,
            devise_texte
        )

    display_montant_devise.short_description = "Montant"

    # FILTRE : Uniquement les employés avec est_approbateur=True
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employe_responsable":
            kwargs["queryset"] = Employe.objects.filter(est_approbateur=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # CORRECTION EXPORT : Gestion de l'ordre des arguments pour éviter le TypeError
    def get_export_filename(self, request, queryset, file_format):
        date_str = timezone.now().strftime('%d-%m-%Y')
        return f"Rapport_Depenses_{date_str}.{file_format.get_extension()}"

    # AUTO-ENREGISTREMENT de l'utilisateur qui crée la dépense
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.enregistre_par = request.user
        super().save_model(request, obj, form, change)


#admin pour paiement des employe
from django.contrib import admin
from django.utils import timezone
from django.contrib.auth.models import User
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ExportMixin

# Importation des modèles nécessaires
from .models import PaiementEmploye
from societe.models import Employe


# ==========================================
# 1. RESSOURCE (LOGIQUE D'EXPORTATION EXCEL)
# ==========================================

class PaiementEmployeResource(resources.ModelResource):
    # On définit des colonnes explicites pour éviter tout conflit de nom
    date = fields.Field(attribute='date_paiement', column_name='Date de Paiement')

    # On traverse la relation : Employe -> Tiers -> nom/prenoms
    nom_famille = fields.Field(attribute='employe__tiers__nom', column_name='Nom')
    prenom = fields.Field(attribute='employe__tiers__prenoms', column_name='Prénom')

    montant_paye = fields.Field(attribute='montant', column_name='Montant')

    user_audit = fields.Field(
        attribute='enregistre_par',
        column_name='Enregistré par',
        widget=ForeignKeyWidget(User, 'username')
    )

    class Meta:
        model = PaiementEmploye
        # On définit exactement l'ordre des colonnes dans le fichier Excel
        fields = ('date', 'nom_famille', 'prenom', 'montant_paye', 'motif', 'user_audit')
        export_order = fields


# ==========================================
# 2. CONFIGURATION DE L'INTERFACE ADMIN
# ==========================================

@admin.register(PaiementEmploye)
class PaiementEmployeAdmin(ExportMixin, admin.ModelAdmin):
    """
    Admin pour PaiementEmploye avec :
    - Exportation uniquement (ExportMixin)
    - Recherche par nom/prénom via Tiers
    - Audit automatique de l'utilisateur
    """
    resource_class = PaiementEmployeResource

    # Configuration de la liste dans l'admin
    # Note : 'employe' utilisera le __str__ que vous avez corrigé dans models.py
    list_display = ('date_paiement', 'employe', 'montant', 'motif', 'enregistre_par')
    list_filter = ('date_paiement', 'employe')

    # Recherche à travers la relation OneToOneField tiers
    search_fields = ('motif', 'employe__tiers__nom', 'employe__tiers__prenoms')

    # Champs verrouillés (audit)
    readonly_fields = ('date_creation', 'enregistre_par')

    # Gestion du nom du fichier d'export
    def get_export_filename(self, request, queryset, file_format):
        date_str = timezone.now().strftime('%d-%m-%Y')
        return f"Paiements_Employes_{date_str}.{file_format.get_extension()}"

    # Injection du placeholder dans le formulaire de saisie
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'motif':
            field.widget.attrs['placeholder'] = "Ex: Salaire Mars 2026, Bonus..."
        return field

    # Enregistrement automatique de l'utilisateur connecté
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Si c'est une création
            obj.enregistre_par = request.user
        super().save_model(request, obj, form, change)