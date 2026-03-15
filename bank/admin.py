from datetime import date, timedelta
from django.contrib import admin
from django.http import JsonResponse
from django.urls import reverse, path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.core.exceptions import ObjectDoesNotExist
import json
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from django.core.exceptions import ObjectDoesNotExist
from .models import Pret, Paiement
from import_export.admin import ImportExportModelAdmin, ExportMixin

from .models import Pret, Paiement, Client
from societe.models import Company, Employe
from bank.views import client_render_pdf_view
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget


# --- FONCTION UTILITAIRE POUR LA MONNAIE ---
def get_company_currency():
    try:
        company = Company.objects.first()
        if company and company.currency:
            return str(company.currency)
    except:
        pass
    return ""


def _format_money_safe(value):
    try:
        return "{:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return "0.00"


# --- I. LOGIQUE DASHBOARD ---
def get_client_stats():
    query_data = (
        Client.objects
        .filter(statut_dossier='VALIDE', montant_pret_actuel__gt=0)
        .values('agent_responsable__tiers__nom', 'agent_responsable__tiers__prenoms')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    labels = []
    data = []
    for item in query_data:
        nom = item['agent_responsable__tiers__nom'] or ""
        prenom = item['agent_responsable__tiers__prenoms'] or ""
        labels.append(f"{nom.upper()} {prenom}".strip() or "Sans Agent")
        data.append(item['total'])
    return {"labels": labels, "data": data}


original_index = admin.site.index


def custom_index(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context['chart_data'] = json.dumps(get_client_stats())
    return original_index(request, extra_context)


admin.site.index = custom_index
admin.site.index_template = 'admin/index.html'


# --- II. ADMIN CLIENT ---
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('actions_pdf', 'get_code', 'get_nom', 'statut_colore', 'agent_responsable', 'get_credit_status',
                    'get_capacite_visuelle', 'date_dernier_pret')
    search_fields = ['tiers__nom', 'tiers__prenoms', 'tiers__code']

    list_display_links = ("get_code", 'get_nom')

    readonly_fields = ('montant_pret_actuel', 'date_dernier_pret', 'date_blocage', 'date_creation', 'date_update',
                       'created_by', 'updated_by', 'logic_js')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """ Filtre pour n'afficher que les approbateurs dans le formulaire Client """
        if db_field.name == "agent_responsable":
            # On applique le filtre sur votre champ BooleanField
            kwargs["queryset"] = Employe.objects.filter(est_approbateur=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:client_id>/pdf/', self.admin_site.admin_view(client_render_pdf_view), name='client-pdf')]
        return custom_urls + urls

    def actions_pdf(self, obj):
        url = reverse('admin:client-pdf', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #447e9b; color: white; padding: 2px 8px; border-radius: 4px;">Imprimer</a>',
            url)

    def get_capacite_visuelle(self, obj):
        valeur = obj.capacite_remboursement
        return format_html('<b style="color: {};">{} {}</b>', "green" if valeur > 0 else "red",
                           _format_money_safe(valeur), get_company_currency())

    def get_credit_status(self, obj):
        curr = get_company_currency()
        if obj.plafond_pret_max > 0:
            ratio = (obj.montant_pret_actuel / obj.plafond_pret_max) * 100
            color = "green" if ratio < 80 else "orange" if ratio <= 100 else "red"
            return format_html('<span style="color: {}; font-weight: bold;">{} / {} ({}%)</span>', color,
                               _format_money_safe(obj.montant_pret_actuel), _format_money_safe(obj.plafond_pret_max),
                               round(ratio, 1))
        return f"{_format_money_safe(obj.montant_pret_actuel)} / 0.00 {curr}"

    def logic_js(self, obj):
        return mark_safe("<script>/* Ta logique JS ici */</script>")

    def get_code(self, obj):
        return obj.tiers.code

    def get_nom(self, obj):
        return f"{obj.tiers.nom.upper()} {obj.tiers.prenoms}"

    def statut_colore(self, obj):
        couleurs = {'INCOMPLET': '#808080', 'EVALUATION': '#3498db', 'VALIDE': '#27ae60', 'BLOQUE': '#e74c3c'}
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 12px; font-weight: bold;">{}</span>',
            couleurs.get(obj.statut_dossier, 'black'), obj.get_statut_dossier_display())

    def save_model(self, request, obj, form, change):
        if not obj.pk: obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class StatutGlobalFilter(admin.SimpleListFilter):
    title = _('État du dossier')
    parameter_name = 'etat'

    def lookups(self, request, model_admin):
        return (
            ('solde', _('✅ Soldé')),
            ('en_cours', _('⏳ En cours (À jour)')),
            ('retard', _('🔴 En Retard (Date dépassée)')),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'solde':
            return queryset.filter(is_solde=True)

        if self.value() == 'en_cours':
            # Non soldé ET date de fin non encore atteinte
            ids = [p.id for p in queryset if not p.is_solde and (not p.date_fin_prevue or p.date_fin_prevue >= today)]
            return queryset.filter(id__in=ids)

        if self.value() == 'retard':
            # Non soldé ET date de fin dépassée
            ids = [p.id for p in queryset if not p.is_solde and p.date_fin_prevue and p.date_fin_prevue < today]
            return queryset.filter(id__in=ids)


class PretResource(resources.ModelResource):
    # On définit des champs personnalisés pour l'export (ex: nom du client au lieu de l'ID)
    client = fields.Field(
        column_name='Client',
        attribute='client',
        widget=ForeignKeyWidget(None, 'tiers__nom')  # Remplacez par le bon modèle si nécessaire
    )

    # Exporter des propriétés calculées
    total_a_payer = fields.Field(attribute='total_a_payer', column_name='Capital Final')
    solde_restant = fields.Field(attribute='solde_restant', column_name='Solde Actuel')
    date_fin = fields.Field(attribute='date_fin_prevue', column_name='Fin Prévue')

    class Meta:
        model = Pret
        # Liste des champs à inclure dans le fichier Excel
        fields = ('code_pret', 'client', 'montant_accorde', 'frais_dossier_pct',
                  'total_a_payer', 'solde_restant', 'date_fin', 'is_solde')
        export_order = fields
# --- III. ADMIN PRET ---
@admin.register(Pret)
class PretAdmin(ImportExportModelAdmin):
    resource_class = PretResource  # <--- Liaison avec la ressource
    list_display = ('bouton_pdf','code_pret', 'link_client', 'display_montant','display_total_initial','agent_responsable','date_creation', 'display_penalites','display_frais', 'display_total_final',
                    'display_echeance', 'display_date_fin', 'is_solde_status')
    search_fields = ('code_pret','client__tiers__code','date_creation', 'client__tiers__nom', 'client__tiers__prenoms')
    #autocomplete_fields = ['client']
    list_per_page = 25
    list_filter = (StatutGlobalFilter, 'frequence_paiement','jour_remboursement', 'date_pret', 'agent_responsable')
    list_display_links = ("code_pret",)
    readonly_fields = ('agent_responsable','display_total_initial','frais_dossier_pct',
                       'display_echeance','display_echeancier',
                       'display_penalites', 'display_total_final','display_debut',
                       'display_date_fin', 'date_creation', 'date_modification', 'display_createur',
                       'display_modificateur')


    def bouton_pdf(self, obj):
        # On génère l'URL vers la vue définie dans ProjectBank/urls.py
        url = reverse('imprimer_contrat_pret', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" '
            'style="background-color: #79aec8; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">'
            '📄Contrat</a>',
            url
        )

    bouton_pdf.short_description = "Contrat"

    def display_echeancier(self, obj):
        if not obj.date_premiere_echeance:
            return "Dates non définies"

        # On prépare les lignes d'abord
        rows_html = ""
        intervalle = {'JOUR': 1, 'SEMAINE': 7, 'MOIS': 30}.get(obj.frequence_paiement, 7)
        nb_payes = obj.paiements.count()

        for i in range(obj.duree):
            date_ech = obj.date_premiere_echeance + timedelta(days=i * intervalle)

            if i < nb_payes:
                statut = '<span style="color:green; font-weight:bold;">✅ Payé</span>'
                couleur_ligne = 'background-color: #e6fffa;'
            elif i == nb_payes:
                statut = '<span style="color:orange; font-weight:bold;">🕒 Prochaine</span>'
                couleur_ligne = 'background-color: #fffaf0; border: 2px solid orange;'
            else:
                statut = '<span style="color:gray;">En attente</span>'
                couleur_ligne = ''

            # On construit la ligne en f-string AVANT le format_html
            rows_html += f"""
                <tr style="{couleur_ligne}">
                    <td>{i + 1}</td>
                    <td>{date_ech.strftime('%d/%m/%Y')}</td>
                    <td>{obj.montant_echeance:.2f}</td>
                    <td>{statut}</td>
                </tr>
            """

        # On utilise format_html sur la structure globale
        # On utilise mark_safe pour les lignes car elles sont déjà construites proprement
        return format_html(
            '<table style="width:100%; text-align:left; border-collapse: collapse;">'
            '<tr style="background:#f8f8f8;"><th>N°</th><th>Date Prévue</th><th>Montant</th><th>Statut</th></tr>'
            '{}'
            '</table>',
            mark_safe(rows_html)  # C'est ici qu'on passe l'argument manquant !
        )

    def display_montant(self, obj):
        # 1. On récupère la valeur ou 0
        montant = obj.montant_accorde or 0

        # 2. Formatage : séparateur de milliers et 2 décimales
        # Ex: 12500.5 -> "12,500.50 HTG"
        montant_formate = "{:,.2f}".format(montant)

        # 3. Rendu HTML (en gras noir pour le distinguer des frais rouges)
        return format_html('<span style="font-weight: bold; color: #333;">{}</span>', montant_formate)

    # Configuration de la colonne
    display_montant.short_description = "Montant"



    def display_total_final(self, obj):
        # CORRECTION : Utilisation de _format_money_safe au lieu de self._format_money
        valeur_actuelle = obj.solde_restant
        txt = _format_money_safe(valeur_actuelle)
        couleur = "#27ae60" if valeur_actuelle <= 0 else "#2c3e50"
        return format_html('<span style="color:{}; font-weight:bold; font-size:1.1em;">{}</span>', couleur, txt)

    display_total_final.short_description = "Solde"

    def display_penalites(self, obj):
        val = obj.montant_penalites_accumulees
        if val > 0:
            return format_html('<span style="color:#c0392b; font-weight:bold;">+ {}</span>', _format_money_safe(val))
        return mark_safe('<span style="color:#bdc3c7;">0.00</span>')

    display_penalites.short_description = "Penalité"

    def display_total_initial(self, obj):
        return format_html('<span style="color:#7f8c8d;">{}</span>', _format_money_safe(obj.total_a_payer))

    display_total_initial.short_description = "Capital final"

    def display_echeance(self, obj):
        unite = {'JOUR': 'jr', 'SEMAINE': 'sem', 'MOIS': 'mois'}.get(obj.frequence_paiement, 'sem')
        return format_html('<strong>{}</strong> <small>/{}</small>', _format_money_safe(obj.montant_echeance), unite)

    display_echeance.short_description = "échéance"

    def is_solde_status(self, obj):
        # Test Date fixe pour tes tests
        #test_date = date(2026, 7, 29)
        test_date=timezone.now().date()
        if obj.is_solde:
            return mark_safe(
                '<span style="background:#27ae60; color:white; padding:3px 10px; border-radius:10px;">SOLDÉ</span>')


        if obj.date_fin_prevue and test_date > obj.date_fin_prevue:
            jours = (test_date - obj.date_fin_prevue).days
            if jours > 90:
                return mark_safe(
                    f'<span style="background:black; color:#ff4d4d; padding:3px 10px; border-radius:10px; border:1px solid red;">🚨 CONTENTIEUX ({jours}j)</span>')
            return mark_safe(
                f'<span style="background:#c0392b; color:white; padding:3px 10px; border-radius:10px;">⚠️ RETARD ({jours}j)</span>')

        return mark_safe(
            '<span style="background:#e67e22; color:white; padding:3px 10px; border-radius:10px;">EN COURS</span>')

    is_solde_status.short_description = "Statut"


    def display_debut(self, obj):
        d = obj.date_premiere_echeance
        return d.strftime('%d/%m/%Y') if d else "---"
    display_debut.short_description = "1er Vers."

    def display_date_fin(self, obj):
        d = obj.date_fin_prevue
        return d.strftime('%d/%m/%Y') if d else "---"
    display_date_fin.short_description = "Fin Prévue"

    def link_client(self, obj):
        url = reverse("admin:bank_client_change", args=[obj.client.id])
        return format_html('<a href="{}" style="font-weight:bold;">{}</a>', url, str(obj.client))

    link_client.short_description = "Client"

    def display_frais(self, obj):
        # On récupère la valeur ou 0 si c'est vide
        return obj.frais_dossier_pct or 0

    # Personnalisation de l'en-tête de la colonne
    display_frais.short_description = "Frais Dossier"

    def display_createur(self, obj):
        return obj.cree_par.username if obj.cree_par else "Système"

    def display_modificateur(self, obj):
        return obj.modifie_par.username if obj.modifie_par else "---"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.cree_par = request.user
        obj.modifie_par = request.user
        super().save_model(request, obj, form, change)

    fieldsets = (
        ('Informations Générales', {'fields': ('client','avaliste', 'montant_accorde',
                                               'duree','frequence_paiement', 'jour_remboursement',
                                               'taux_interet', 'taux_penalite','frais_dossier_pct','date_creation'
                                               )}),
        ('Suivi des Échéances', {
            'fields': ('display_echeancier',),
            'description': "Ce tableau se met à jour après chaque remboursement validé."
        }),
    )



# --- IV. ADMIN PAIEMENT ---
class PaiementResource(resources.ModelResource):
    # --- Champs pour le Client du Prêt ---
    code_client = fields.Field(attribute='pret__client__tiers__code', column_name='Code Client')
    nom_client = fields.Field(column_name='Nom Client')

    # --- Champs pour le Prêt ---
    code_pret = fields.Field(attribute='pret__code_pret', column_name='N° Prêt')

    # --- Champ pour l'Agent (Employé -> Tiers) ---
    nom_agent = fields.Field(column_name='Agent Responsable')

    class Meta:
        model = Paiement
        fields = ('id', 'date_paiement', 'code_client', 'nom_client', 'code_pret',
                  'montant_paye', 'penalite_payee', 'mode_paiement', 'nom_agent')
        export_order = fields

    def dehydrate_nom_client(self, obj):
        if obj.pret and obj.pret.client and obj.pret.client.tiers:
            t = obj.pret.client.tiers
            return f"{t.nom} {t.prenoms}"
        return "N/A"

    def dehydrate_nom_agent(self, obj):
        # On remonte : Paiement -> Employe -> Tiers
        try:
            if obj.agent_responsable and obj.agent_responsable.tiers:
                t = obj.agent_responsable.tiers
                return f"{t.nom} {t.prenoms}"
        except AttributeError:
            pass
        return "N/A"
@admin.register(Paiement)
class PaiementAdmin(ExportMixin,admin.ModelAdmin):
    resource_class = PaiementResource  # <--- Liaison avec la ressource
    # --- 1. Configuration de l'affichage ---
    list_display = ('date_paiement', 'display_pret','get_code_tiers'
                        ,'get_client', 'display_montant', 'display_penalite',
                    'mode_paiement', 'agent_responsable', 'display_modificateur')
    search_fields = ('pret__code_pret','pret__client__tiers__code', 'pret__client__tiers__nom',
                     'pret__client__tiers__prenoms')
    list_filter = (
        ('date_paiement', admin.DateFieldListFilter),
        ('date_creation', admin.DateFieldListFilter),
        'agent_responsable',
        'mode_paiement',
    )
    readonly_fields = ('agent_responsable','date_paiement', 'date_creation',
                       'date_modification', 'display_createur', 'display_modificateur')

    # --- 2. Liaison du fichier JavaScript ---
    class Media:
        js = ('js/admin_paiement.js',)



    def get_client(self, obj):
        # On remonte du Paiement -> Pret -> Client -> Tiers (nom et prenoms)
        if obj.pret and obj.pret.client and obj.pret.client.tiers:
            # Correction ici : prenoms avec un 's'
            return f"{obj.pret.client.tiers.nom} {obj.pret.client.tiers.prenoms}"
        return "N/A"

    get_client.short_description = 'Client'
    get_client.admin_order_field = 'pret__client__tiers__nom'

    # 1. Récupérer le CODE depuis le TIERS
    def get_code_tiers(self, obj):
        if obj.pret and obj.pret.client and obj.pret.client.tiers:
            return obj.pret.client.tiers.code
        return "---"

    get_code_tiers.short_description = 'Code Client'  # Label de la colonne

    # --- 3. Gestion des URLs personnalisées pour l'AJAX ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Cette URL permet au JS d'appeler la fonction get_next_date
            path('get-next-date/', self.admin_site.admin_view(self.get_next_date), name='get_next_date'),
        ]
        return custom_urls + urls

    def get_next_date(self, request):
        pret_id = request.GET.get('pret_id')
        try:
            pret = Pret.objects.get(pk=pret_id)
            prochaine_date = pret.get_prochaine_date_echeance()
            heure_actuelle = timezone.now().strftime('%H:%M:%S')

            return JsonResponse({
                'success': True,
                'next_date': prochaine_date.strftime('%Y-%m-%d'),
                'next_time': heure_actuelle,
            })
        except (Pret.DoesNotExist, ValueError, AttributeError):
            return JsonResponse({'success': False, 'next_date': None})

    # --- 4. Logique du formulaire ---
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "pret":
            kwargs["queryset"] = Pret.objects.filter(is_solde=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['penalite_payee'].help_text = (
            "Le montant saisi doit correspondre au centime près au calcul du système."
        )
        return form

    # --- 5. Affichage personnalisé (Colonnes) ---
    def display_pret(self, obj):
        try:
            return obj.pret.code_pret if obj.pret else "---"
        except (ObjectDoesNotExist, AttributeError):
            return mark_safe("<span style='color:red;'>Prêt manquant</span>")
    display_pret.short_description = "N° Prêt"

    def display_montant(self, obj):
        # Utilise ta fonction de formatage d'argent ici
        return format_html('<span style="color:green; font-weight:bold;">{}</span>', obj.montant_paye)
    display_montant.short_description = "Somme Versée"

    # Si vous voulez quand même un petit formatage propre sans HTML :
    def display_penalite(self, obj):
        valeur = obj.penalite_payee or 0
        return f"{valeur:,.2f}"

    display_penalite.short_description = "Pénalité"

    # --- 6. Sauvegarde et Audit ---
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.cree_par = request.user
        obj.modifie_par = request.user
        super().save_model(request, obj, form, change)

    def display_createur(self, obj):
        return obj.cree_par.username if obj.cree_par else "Système"
    display_createur.short_description = "Créé par"

    def display_modificateur(self, obj):
        return obj.modifie_par.username if obj.modifie_par else "---"
    display_modificateur.short_description = "Modifié par"

    # --- 7. Mise en page (Fieldsets) ---
    fieldsets = (
        ('Détails du Remboursement', {
            'fields': ('pret', 'date_paiement', 'montant_paye', 'mode_paiement', 'penalite_payee')
        }),
        ('Traçabilité', {
            'fields': (
                'agent_responsable',
                ('display_createur', 'date_creation'),
                ('display_modificateur', 'date_modification')
            ),
            'classes': ('collapse',), # Masque cette section par défaut
        }),
    )