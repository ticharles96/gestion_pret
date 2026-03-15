from django.contrib import admin
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_countries.widgets import CountrySelectWidget
from django_countries.fields import CountryField  # <--- Importez bien la classe du champ
from admin_auto_filters.filters import AutocompleteFilter
from django import forms
from django_select2.forms import ModelSelect2Widget
from .models import Departement, Ville, Adresse, Pays, Currency
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import admin
from django.forms import SelectDateWidget
from django.db import models
import datetime


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    # On affiche les champs calculés dans la liste
    list_display = ('name', 'code', 'symbol', 'exchange_rate', 'is_default', 'created_at','updated_at','created_by')
    search_fields = ['name', 'symbol', ]
    # On permet de les voir dans le formulaire sans pouvoir les modifier
    readonly_fields = ('code', 'symbol')

    def save_model(self, request, obj, form, change):
        if not change:
            # Si c'est une création, on enregistre l'auteur
            obj.created_by = request.user

        # Dans tous les cas (création ou modif), on enregistre le dernier modificateur
        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

class VilleSelect2Widget(ModelSelect2Widget):
    model = Ville
    search_fields = ['nom__icontains']
    dependent_fields = {'departement': 'departement'}

    def filter_queryset(self, request, term, queryset=None, **kwargs):
        """
        Cette méthode est celle utilisée par la vue AJAX de Select2.
        Elle possède l'argument 'request', ce qui évite votre erreur précédente.
        """
        # On récupère l'ID du département depuis la requête AJAX
        dep_id = request.GET.get("departement")

        # Si aucun département n'est envoyé (au départ ou si vidé), on renvoie une liste vide
        if not dep_id:
            return self.get_queryset().none()

        # Sinon, on filtre normalement
        return super().filter_queryset(request, term, queryset, **kwargs)


class AdresseForm(forms.ModelForm):
    class Meta:
        model = Adresse
        fields = '__all__'
        widgets = {
            'ville': VilleSelect2Widget(
                attrs={
                    "data-placeholder": "Sélectionnez d'abord un département",
                    "data-minimum-input-length": "0",
                },
            )
        }

@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    pass

@admin.register(Pays)
class VilleAdmin(admin.ModelAdmin):
    formfield_overrides = {
        CountryField: {'widget': CountrySelectWidget},
    }
    #list_display = ('nom',)
    list_display = ('nom', )

    def afficher_drapeau(self, obj):
        # obj.pays.flag renvoie l'URL de l'image du drapeau
        if obj.nom:
            return format_html(
                '<img src="{}" style="width: 20px; height: auto;" />',
                obj.nom.flag
            )
        return ""

    afficher_drapeau.short_description = "Drapeau"  # Titre de la colonne

class DepartementFilter(AutocompleteFilter):
    title = 'Département'
    field_name = 'departement'



@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'departement')
    # Ajoute une barre de recherche en haut (recherche sur le nom de la ville)
    search_fields = ('nom',)

    # Ajoute un volet de filtrage à droite par département
    list_filter = ('departement',)

    # Optimisation : charge les relations en une seule requête SQL
    list_select_related = ('departement',)





