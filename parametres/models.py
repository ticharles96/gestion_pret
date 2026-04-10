from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django_countries.fields import CountryField
from smart_selects.db_fields import ChainedForeignKey
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _



class Pays(models.Model):
    nom =CountryField(
        blank_label="Sélectionnez un pays", # Texte affiché quand vide
        null=True,
        blank=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="créer par",
        editable=False  # Optionnel : empêche l'affichage partout
    )

    class Meta:
        # Nom affiché pour un seul objet (ex: "Ajouter un Département")
        verbose_name = "Pays"

        # Nom affiché dans le menu latéral et les titres de listes
        verbose_name_plural = "Pays"

    def __str__(self):
        return self.nom.name

class Departement(models.Model):
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT)
    nom = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="créer par",
        editable=False  # Optionnel : empêche l'affichage partout
    )
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['nom', 'pays'],
                name='unique_ville_pays'
            )
        ]
        # Nom affiché pour un seul objet (ex: "Ajouter un Département")
        verbose_name = "Département"

        # Nom affiché dans le menu latéral et les titres de listes
        verbose_name_plural = "Départements"

    def __str__(self):
        return self.nom


class Ville(models.Model):
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="créer par",
        editable=False  # Optionnel : empêche l'affichage partout
    )
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['departement', 'nom'],
                name='unique_ville_departement'
            )
        ]
        # Nom affiché pour un seul objet (ex: "Ajouter un Département")
        verbose_name = "Ville"

        # Nom affiché dans le menu latéral et les titres de listes
        verbose_name_plural = "Villes"



    def __str__(self):
        return self.nom


class Adresse(models.Model):
    departement = models.ForeignKey(Departement, on_delete=models.PROTECT)
    ville = ChainedForeignKey(
        Ville,
        chained_field="departement",      # Nom du champ dans ce modèle
        chained_model_field="departement",# Nom du champ dans le modèle Ville
        show_all=False,
        auto_choose=True,
        sort=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="créer par",
        editable=False  # Optionnel : empêche l'affichage partout
    )

    class Meta:
        # Nom affiché pour un seul objet (ex: "Ajouter un Département")
        verbose_name = "Adresse"

        # Nom affiché dans le menu latéral et les titres de listes
        verbose_name_plural = "Adresses"
    def __str__(self):
        return f" {self.departement}, {self.ville}, {self.departement.pays.nom}"


class Currency(models.Model):
    # Dictionnaire de configuration (Code: Symbole)
    CURRENCY_DATA = {
        'HTG': ('Gourde Haïtienne', 'G'),
        'USD': ('Dollar Américain', '$'),
        'EUR': ('Euro', '€'),
        '$HT': ('Dollar Haïtien', '$HT'),
        'CAD': ('Dollar Canadien', 'CA$'),
        'DOP': ('Peso Dominicain', 'RD$'),
    }

    # Génère : [('HTG', 'Gourde Haïtienne'), ('USD', 'Dollar Américain'), ...]
    CURRENCY_CHOICES = [(code, data[0]) for code, data in CURRENCY_DATA.items()]
    name = models.CharField(_("Devise"), max_length=3, choices=CURRENCY_CHOICES, unique=True)
    code = models.CharField(_("Code ISO"), max_length=3, unique=True, editable=False)  # Masqué car auto
    symbol = models.CharField(_("Symbole"), max_length=10, editable=False)  # Masqué car auto

    exchange_rate = models.DecimalField(_("Taux"), max_digits=15, decimal_places=4, default=1.0000)
    is_default = models.BooleanField(_("Par défaut"), default=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="modifiée  le")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="crée par",
        editable=False  # Optionnel : empêche l'affichage partout
    )
    class Meta:
        verbose_name = _("Monnaie")
        verbose_name_plural = _("Monnaies")

    def save(self, *args, **kwargs):


        # Extraction automatique depuis le dictionnaire CURRENCY_DATA
        if self.name in self.CURRENCY_DATA:
            self.code = self.name  # Le code ISO est la clé (ex: HTG)
            self.symbol = self.CURRENCY_DATA[self.name][1]  # Récupère le symbole (ex: G)

        # Gestion de l'unicité de la monnaie par défaut
        if self.is_default:
            Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)



        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}"