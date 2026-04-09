import secrets
import string
from datetime import date
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import user_logged_in
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models, transaction
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from smart_selects.db_fields import ChainedForeignKey
from django.core.validators import MinLengthValidator  # Import requis
from phonenumber_field.modelfields import PhoneNumberField


import parametres
from parametres.models import Departement, Ville
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_delete, post_save, m2m_changed  # <--- Importation
from django.dispatch import receiver

# Create your models here.



class Company(models.Model):
    # Dans votre modèle Company
    LEGAL_STATUS_CHOICES = [
        ('IND', 'Entreprise Individuelle'),
        ('SARL', 'S.A.R.L (Soc. à Responsabilité Limitée)'),
        ('SA', 'S.A (Société Anonyme)'),
        ('ONG', 'Organisation Non Gouvernementale'),
    ]
    # --- Identité Visuelle ---
    name = models.CharField(_("Nom de l'entreprise"), validators=[MinLengthValidator(3)], max_length=255)
    sigle = models.CharField(_("Sigle de l'entreprise") , validators=[MinLengthValidator(3)], max_length=20)
    logo = models.ImageField(_("Logo Officiel"), upload_to='company/logos/')
    slogan = models.CharField(_("Slogan"), validators=[MinLengthValidator(3)], max_length=255, blank=True, null=True)

    # --- Coordonnées de Contact (pour l'en-tête) ---
    email_contact = models.EmailField(_("Email de contact"))

    website = models.URLField(_("Site Web"), blank=True, null=True)

    # --- Monnaie Libre ---
    # Ici, vous pouvez écrire "$ HT", "USD", "Gourdes", etc.
    currency = models.ForeignKey('parametres.Currency', on_delete=models.PROTECT, null=True)

    default_interest_rate = models.DecimalField(
        "Taux d'intérêt Pret (%)",
        max_digits=20,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    interet_maison_daffaire = models.DecimalField(
        "Taux d'intérêt Maison d'affaire(%)",
        max_digits=20,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # --- Frais de Retard Libres ---
    late_fee_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        verbose_name="Frais de Retard"
    )

    # --- Informations Légales (Indispensables pour les rapports officiels) ---
    tax_id = models.CharField(_("NIF / Matricule Fiscale"), blank=True, null=True, max_length=100, unique=True)
    legal_status = models.CharField(
        max_length=10,
        choices=LEGAL_STATUS_CHOICES,
        default='SARL'
    )
    capital = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        verbose_name="Capital Social"
    )
    frais_dossier_pct = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        verbose_name="Frais de dossier (%)",
        help_text="Pourcentage des frais de dossier appliqué à ce client"
    )
    date_creation = models.DateField()

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
        verbose_name = _("Information de l'Entreprise")
        verbose_name_plural = _("Informations de l'Entreprise")

    def __str__(self):
        return self.name



class Phone(models.Model):
    company = models.ForeignKey(
        Company,
        related_name='phones',
        on_delete=models.CASCADE
    )
    label = models.CharField(
        "Étiquette",
        max_length=50,
        help_text="Ex: Bureau, WhatsApp, Urgence"
    )
    phone_number = PhoneNumberField(
    verbose_name="Téléphone",
    # On retire region="FR" pour accepter tous les pays
    blank=False,
    null=False,
    help_text="Entrez le numéro au format international (ex: +509 XXXX XXXX pour Haïti )."
    )

    def __str__(self):
        return f"{self.label}"

class CompanyAddress(models.Model):
    company = models.ForeignKey(
        Company,
        related_name='addresses',
        on_delete=models.CASCADE
    )
    departement = models.ForeignKey(Departement, on_delete=models.PROTECT)
    ville = ChainedForeignKey(
        Ville,
        chained_field="departement",  # Nom du champ dans ce modèle
        chained_model_field="departement",  # Nom du champ dans le modèle Ville
        show_all=False,
        auto_choose=True,
        sort=True
    )

    full_address = models.CharField(verbose_name="Adresse résidentielle", max_length=500)
    is_principal = models.BooleanField("Adresse principale", default=False)

    class Meta:
        verbose_name = "Adresse"
        verbose_name_plural = "Adresses"

    def __str__(self):
        return f"{self.full_address[:30]}..."


class CompanyBank(models.Model):
    CURRENCY_CHOICES = [
        ('HTG', 'Gourdes (HTG)'),
        ('USD', 'Dollars (USD)'),
    ]

    company = models.ForeignKey(
        Company,
        related_name='banks',
        on_delete=models.CASCADE
    )
    bank_name = models.CharField("Nom de la Banque", max_length=100)
    account_holder = models.CharField("Titulaire du Compte", max_length=150,
                                      help_text="Nom exact figurant sur le relevé bancaire")
    account_number = models.CharField("Numéro de Compte", max_length=50)
    account_type = models.CharField("Type de compte", max_length=50)
    currency = models.CharField("Monnaie", max_length=3, choices=CURRENCY_CHOICES, default='HTG')

    class Meta:
        verbose_name = "Information Bancaire"
        verbose_name_plural = "Informations Bancaires"

    def __str__(self):
        return f"{self.bank_name} - {self.currency}"




#method contrainte pour l'age de la personne
def validate_age_minimum(value):
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 18:
        raise ValidationError("La personne doit être âgé d'au moins 18 ans.")


class Tiers(models.Model):
    # Choix pour les champs
    GENRE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
        ('A', 'Autre'),
    ]

    STATUT_MATRIMONIAL_CHOICES = [
        ('C', 'Célibataire'),
        ('M', 'Marié(e)'),
        ('D', 'Divorcé(e)'),
        ('V', 'Veuf/Veuve'),
        ('S', 'Séparé(e)'),
    ]

    TYPE_PIECE_CHOICES = [
        ('NINU', " Numéro d'Identification Nationale Unique"),
        ('PASSEPORT', 'Passeport'),
        ('PERMIS', 'Permis de conduire'),
        ('AUTRES', 'AUTRES'),

    ]

    NIVEAU_ETUDE_CHOICES = [
        ('PRIMAIRE', 'Primaire'),
        ('SECONDAIRE', 'Secondaire'),
        ('BACC', 'Baccalauréat'),
        ('DIPLOME', 'Diplome'),
        ('LICENCE', 'Licence'),
        ('MASTER', 'Master'),
        ('DOCTORAT', 'Doctorat'),
        ('AUTRE', 'Autre'),
    ]
    RELIGION_CHOICES = [
        ('BAPTISTE', 'Baptiste'),
        ('ADVENTISTE', 'Adventiste'),
        ('CATHOLIQUE', 'Catholique'),
        ('JEHOVAH', 'Témoin de Jéhovah'),
        ('MORMON', 'Mormon'),
        ('MUSULMAN', 'Musulman'),
        ('PENTECOTISTE', 'Pentecôtiste'),
        ('PROTESTANT', 'Protestant'),
        ('VODOUISANT', 'Vodouisant'),
        ('AUTRE', 'Autre'),
        ('AUCUNE', 'Aucune / Athée'),
    ]
    # Informations personnelles
    code = models.CharField(
        max_length=20,
        unique=True,
        editable= False,
        verbose_name="Code"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenoms = models.CharField(max_length=100, verbose_name="Prénom")
    date_naissance = models.DateField(verbose_name="Date de naissance", validators=[validate_age_minimum])
    genre = models.CharField(
        max_length=1,
        choices=GENRE_CHOICES,
        verbose_name="Genre"
    )

    statut_matrimonial = models.CharField(
        max_length=1,
        choices=STATUT_MATRIMONIAL_CHOICES,
        verbose_name="Statut matrimonial"
    )
    religion = models.CharField(
        verbose_name="Religion",
        max_length=20,
        choices=RELIGION_CHOICES,
        blank=False,  # Permet de ne pas remplir le champ
        null=True
    )


    email = models.EmailField(verbose_name="Adresse email", unique=True, blank=True)

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

    # Informations complémentaires
    niveau_etude = models.CharField(
        max_length=20,
        choices=NIVEAU_ETUDE_CHOICES,
        verbose_name="Niveau d'étude"
    )

    nombre_enfants = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre d'enfants"
    )



    class Meta:
        # Sécurité : Empêche l'enregistrement d'un même client (Nom + Prénoms + Date)
        constraints = [
            models.UniqueConstraint(
                fields=['nom', 'prenoms', 'date_naissance'],
                name='unique_client_identity'
            )
        ]
        verbose_name = "Tier"
        verbose_name_plural = "Tiers"

    def save(self, *args, **kwargs):
        if not self.code:
            # 1. 2 car. Nom + 2 car. Prénoms (Majuscules)
            prefixe = f"{self.nom[:2].upper()}{self.prenoms[:2].upper()}"

            # 2. Date au format JJMMAAAA
            date_str = self.date_naissance.strftime('%d%m%Y')

            # 3. Assemblage final (ex: DUJE12031990)
            self.code = f"{prefixe}{date_str}"

        super(Tiers, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.code},{self.nom.upper()} {self.prenoms}"

    def photo_tag(self):
        """Affiche la miniature de la photo depuis IdentityDocument"""
        try:
            # On vérifie si la relation OneToOne existe et si la photo est remplie
            if hasattr(self, 'identity_docs') and self.identity_docs.photo:
                return mark_safe(
                    f'<img src="{self.identity_docs.photo.url}" width="35" height="35" style="border-radius: 50%; object-fit: cover;" />')
        except:
            pass
        return mark_safe('<span style="font-size: 18px; color: #999;">👤</span>')

    # AJOUTEZ CETTE MÉTHODE ICI :

class IdentityDocument(models.Model):
    TYPE_PIECE_CHOICES = [
        ('NINU', "Numéro d'Identification Nationale Unique"),
        ('PASSEPORT', 'Passeport'),
        ('PERMIS', 'Permis de conduire'),
        ('AUTRES', 'AUTRES'),
    ]

    # Relation unique vers le Tiers
    tiers = models.OneToOneField(
        'Tiers',
        on_delete=models.PROTECT,
        related_name='identity_docs'
    )

    # Choix du type de document
    type_piece = models.CharField(
        max_length=20,
        choices=TYPE_PIECE_CHOICES,
        blank=False, null=False,
        verbose_name="Type de pièce"
    )
    numero_document = models.CharField(
        max_length=50,
        verbose_name="Numéro de la pièce",
        unique=True,  # Empeche les doublons dans toute la base
        blank=False,
        null=False,
        help_text="Ce numéro doit être unique (NIF, CIN ou Passeport)"
    )

    # Section des fichiers images
    photo = models.ImageField(
        upload_to='clients/photos/',
        verbose_name="Photo d'identité (Profil)",
        blank=True,
        null=True
    )

    piece_identite_recto = models.ImageField(
        upload_to='clients/pieces_identite/',
        verbose_name="Recto / Page principale",
        blank=True,
        null=True
    )

    piece_identite_verso = models.ImageField(
        upload_to='clients/pieces_identite/',
        verbose_name="Verso (laisser vide pour Passeport)",
        blank=True,
        null=True
    )

    signature = models.ImageField(
        upload_to='clients/signatures/',
        verbose_name="Signature",
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Document d'identité"
        verbose_name_plural = "Documents d'identité"

    def __str__(self):
        # Affiche ex: "Passeport - JEAN Pierre" dans l'admin
        return f"{self.get_type_piece_display()} - {self.tiers.nom} {self.tiers.prenoms}"

#Adresses des Tiers
class TiersAdresse(models.Model):
    TYPE_ADRESSE_CHOICES = [
        ('Bureau', 'Bureau'),
        ('Domicile', 'Domicile'),
        ('Business', 'Business'),
        ('Livraison', 'Adresse de livraison'),
        ('Facturation', 'Adresse de facturation'),
    ]

    tiers = models.ForeignKey('Tiers', on_delete=models.CASCADE, related_name='adresses')
    type_adresse = models.CharField(max_length=50, choices=TYPE_ADRESSE_CHOICES)
    departement = models.ForeignKey(Departement, on_delete=models.PROTECT)
    ville = ChainedForeignKey(
        Ville,
        chained_field="departement",  # Nom du champ dans ce modèle
        chained_model_field="departement",  # Nom du champ dans le modèle Ville
        show_all=False,
        auto_choose=True,
        sort=True
    )
    rue = models.CharField(max_length=255)
    est_principale = models.BooleanField(default=False, verbose_name="Principale")
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
        verbose_name = "Adresse"
        constraints = [
            models.UniqueConstraint(
                fields=['tiers', 'type_adresse', 'rue', 'ville','departement'],
                name='unique_adresse_tiers'
            )
        ]

    def __str__(self):
        return f"{self.rue}, {self.ville}"

    def clean(self):
        super().clean()

        # 1. Protection contre les objets non encore liés (évite le crash 500)
        try:
            if not self.tiers_id or not self.departement_id or not self.ville_id:
                return  # On laisse Django afficher "Ce champ est obligatoire"
        except (AttributeError, ObjectDoesNotExist):
            return

        # 2. Vérification des doublons (Maintenant sécurisée car les IDs existent)
        if TiersAdresse.objects.filter(
                tiers=self.tiers,
                type_adresse=self.type_adresse,
                rue=self.rue,
                ville=self.ville,
                departement=self.departement
        ).exclude(pk=self.pk).exists():
            raise ValidationError({
                'rue': "Cette adresse exacte existe déjà pour ce tiers."
            })

    def save(self, *args, **kwargs):
        # On vérifie la présence de la PK du tiers pour la logique métier
        if self.tiers_id and self.tiers.pk:
            # Transaction atomique pour garantir l'intégrité
            with transaction.atomic():
                # Si c'est la première adresse, elle devient principale
                if not TiersAdresse.objects.filter(tiers=self.tiers).exists():
                    self.est_principale = True

                # Si on marque cette adresse comme principale, on décoche les autres
                if self.est_principale:
                    TiersAdresse.objects.filter(
                        tiers=self.tiers,
                        est_principale=True
                    ).exclude(pk=self.pk).update(est_principale=False)

        super().save(*args, **kwargs)

#pour donners principal a autre adresses apres supresiom
@receiver(post_delete, sender=TiersAdresse)
def maj_adresse_principale_apres_suppression(sender, instance, **kwargs):
    # On vérifie si le Tiers existe encore (pour éviter l'erreur lors d'une suppression en cascade)
    try:
        if instance.est_principale and instance.tiers:
            prochaine_adresse = TiersAdresse.objects.filter(tiers=instance.tiers).first()
            if prochaine_adresse:
                prochaine_adresse.est_principale = True
                prochaine_adresse.save()
    except: # Le tiers est probablement en train d'être supprimé aussi
        pass


#Moyens de contact pour les tiers
class Contact(models.Model):
    moyens_CHOICES = [
        ('Telephone Mobile', 'Telephone Mobile'),
        ('Telephone domicile', 'Telephone domicile'),
        ('email', 'Adresse electronique'),
        ('fax', 'fax'),
        ('siteweb', 'Site Web'),
        ('whatsapp', 'Whatsapp'),
        ('facebook', 'Facebook'),
        ('Autre', 'Autre'),
    ]

    tiers = models.ForeignKey('Tiers', on_delete=models.CASCADE, related_name='moyens_contact')
    type_contact = models.CharField(max_length=50, choices=moyens_CHOICES)
    valeur = models.CharField(max_length=255)
    est_principal = models.BooleanField(default=False, verbose_name="Principal")


    def icone_visuelle(self):
        if not self.valeur:
            return mark_safe('<i class="fa-solid fa-circle-info" style="color: #ccc;"></i>')

        icones = {
            'Telephone Mobile': ('fa-mobile-screen', '#417690', 'tel:'),
            'Telephone domicile': ('fa-phone', '#417690', 'tel:'),
            'email': ('fa-envelope', '#EA4335', 'mailto:'),
            'fax': ('fa-fax', '#666', 'tel:'),
            'siteweb': ('fa-globe', '#007bff', ''),
            'whatsapp': ('fa-whatsapp', '#25D366', 'https://wa.me/'),
            'facebook': ('fa-facebook', '#1877F2', ''),
        }

        icon_class, color, prefix = icones.get(self.type_contact, ('fa-circle-info', '#ccc', ''))

        # Construction du lien
        href = f"{prefix}{self.valeur}"

        return mark_safe(
            f'<a href="{href}" target="_blank" title="Ouvrir {self.valeur}" class="contact-link">'
            f'<i class="fa-solid {icon_class}" style="font-size: 1.2rem; color: {color};"></i>'
            f'</a>'
        )

    icone_visuelle.short_description = "Action"

    def clean(self):
        super().clean()
        # Sécurité pour les nouveaux Tiers
        if not self.tiers_id or not self.tiers.pk:
            return

        # Votre logique de validation email/tel ici...
        if Contact.objects.filter(tiers=self.tiers, type_contact=self.type_contact, valeur=self.valeur).exclude(
                pk=self.pk).exists():
            raise ValidationError({'valeur': "Ce contact existe déjà."})

    def save(self, *args, **kwargs):
        if self.est_principal and self.tiers_id and self.tiers.pk:
            Contact.objects.filter(tiers=self.tiers, est_principal=True).exclude(pk=self.pk).update(est_principal=False)
        super().save(*args, **kwargs)

    class Meta:

        verbose_name = "Moyen de contact"
        verbose_name_plural = "Moyens de contact"
        constraints = [
            models.UniqueConstraint(
                fields=['tiers', 'type_contact', 'valeur'],
                name='unique_contact_par_tiers'
            )
        ]



    def save(self, *args, **kwargs):
        if self.est_principal:
            # On utilise une transaction pour s'assurer que l'opération est atomique
            with transaction.atomic():
                # On met à False tous les autres contacts de ce tiers
                Contact.objects.filter(tiers=self.tiers, est_principal=True).update(est_principal=False)
        super().save(*args, **kwargs)
    def __str__(self):
        return f""


@receiver(post_delete, sender=Contact)
def maj_contact_principal_apres_suppression(sender, instance, **kwargs):
    """
    Si on supprime le contact qui était principal, on en désigne un nouveau
    automatiquement parmi les contacts restants (priorité aux téléphones).
    """
    try:
        if instance.est_principal and instance.tiers:
            # On cherche un remplaçant, de préférence un téléphone
            types_tel = ['Telephone Mobile', 'Telephone domicile', 'whatsapp']

            # On cherche d'abord s'il reste un téléphone
            prochain = Contact.objects.filter(
                tiers=instance.tiers,
                type_contact__in=types_tel
            ).first()

            # Sinon, on prend n'importe quel autre moyen de contact restant
            if not prochain:
                prochain = Contact.objects.filter(tiers=instance.tiers).first()

            if prochain:
                prochain.est_principal = True
                prochain.save()
    except:
        # Cas où le Tiers lui-même est en cours de suppression
        pass


# Modele pour employe
class Employe(models.Model):
    # Relation avec l'identité civile (Tiers)
    tiers = models.OneToOneField(
        'Tiers',
        on_delete=models.PROTECT,
        related_name='profil_employe'
    )

    # Relation avec le compte de connexion Django
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Compte Utilisateur",
        related_name='profil_employe'  # Nom unique
    )

    # Relation multiple pour les postes (Groupes Django)
    poste = models.ManyToManyField(
        Group,
        verbose_name="Postes / Groupes d'accès",
        help_text="Maintenez CTRL pour en sélectionner plusieurs"
    )

    est_approbateur = models.BooleanField(
        default=False,
        verbose_name="Droit d'approbation"
    )

    date_embauche = models.DateField(verbose_name="Date d'embauche")
    doit_changer_mot_de_passe = models.BooleanField(default=True, verbose_name="Doit changer de MDP")
    salaire_base = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.01'))],  # Minimum 0.01
        help_text="Le salaire doit être supérieur à 0."
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="créer le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiier le")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="créer par",
        editable=False,  # Optionnel : empêche l'affichage partout
        related_name = 'employes_crees'  # Nom unique
    )


    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        with transaction.atomic():
            # Username logic
            if self.tiers.email and '@' in self.tiers.email:
                nouveau_username = self.tiers.email.split('@')[0].lower()
            else:
                nouveau_username = self.tiers.code.lower()

            password_genere = None

            if not self.user:
                # GÉNÉRATION MANUELLE SÉCURISÉE (Remplace make_random_password)
                alphabet = string.ascii_letters + string.digits
                password_genere = ''.join(secrets.choice(alphabet) for i in range(10))

                # Création de l'utilisateur avec le mot de passe généré
                new_user = User.objects.create_user(
                    username=nouveau_username,
                    email=self.tiers.email,
                    first_name=self.tiers.prenoms,
                    last_name=self.tiers.nom,
                    password=password_genere
                )
                new_user.is_staff = True
                new_user.save()
                self.user = new_user

            # Sauvegarde de l'employé
            super().save(*args, **kwargs)

            # Envoi du mail
            if is_new and password_genere and self.tiers.email:
                self.envoyer_mail_bienvenue(nouveau_username, password_genere)

    def envoyer_mail_bienvenue(self, username, password):
        company = Company.objects.first()

        # Données par défaut
        company_name = company.name if company else "Notre Entreprise"
        company_website = company.website if company and company.website else "http://127.0.0.1:8000"
        logo_url = ""

        if company and company.logo:
            # On construit l'URL complète du logo
            logo_url = f"{company_website}{company.logo.url}"

        sujet = f"Bienvenue chez {company_name} - Vos accès"
        from_email = settings.EMAIL_HOST_USER
        to = self.tiers.email

        # 1. Le corps du message en HTML
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <img src="{logo_url}" alt="{company_name}" style="max-width: 150px; height: auto;">
                    </div>

                    <h2 style="color: #2c3e50; text-align: center;">Bienvenue dans l'équipe !</h2>

                    <p>Bonjour <strong>{self.tiers.prenoms}</strong>,</p>
                    <p>Nous sommes ravis de vous compter parmi nous. Votre compte employé a été configuré avec les accès suivants :</p>

                    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>Identifiant :</strong> {username}</p>
                        <p style="margin: 5px 0;"><strong>Mot de passe temporaire :</strong> {password}</p>
                    </div>

                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{company_website}/admin" 
                           style="background-color: #3498db; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           Se connecter à la plateforme
                        </a>
                    </div>

                    <p style="margin-top: 30px; font-size: 12px; color: #7f8c8d; text-align: center;">
                        {company_name} - {company.email_contact if company else ''}<br>
                        {company_website}
                    </p>
                </div>
            </body>
        </html>
        """

        # 2. Version texte brut (pour les vieux clients mail ou la sécurité)
        text_content = strip_tags(html_content)

        try:
            # Création de l'email multi-format
            msg = EmailMultiAlternatives(sujet, text_content, from_email, [to])
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
        except Exception as e:
            print(f"Erreur d'envoi email HTML : {e}")

    def __str__(self):
        """
        Représentation textuelle sécurisée pour éviter les RecursionError
        et les ValueError sur le ManyToMany.
        """
        info_tiers = f"{self.tiers.nom.upper()} {self.tiers.prenoms}"

        # On ne lit le ManyToMany que si l'objet est déjà enregistré (possède un ID)
        if self.pk:
            try:
                # Récupère les noms des groupes sélectionnés
                noms_postes = ", ".join([g.name for g in self.poste.all()])
                if noms_postes:
                    return f"{info_tiers}"
            except Exception:
                pass

        return info_tiers



#pour ajouter poste a utilisateur a chaque creation employe
@receiver(m2m_changed, sender=Employe.poste.through)
def sync_user_postes(sender, instance, action, **kwargs):
    """
    Synchronise les groupes de l'User Django avec les postes choisis.
    S'exécute après la sauvegarde des relations ManyToMany.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        if instance.user:
            # On remplace tous les groupes de l'utilisateur par les postes actuels
            instance.user.groups.set(instance.poste.all())

#pour supprimer un utilisateur lors de la supression de l'employe
@receiver(post_delete, sender=Employe)
def delete_user_with_employe(sender, instance, **kwargs):
    """
    Supprime le compte User associé dès que l'Employé est supprimé.
    """
    if instance.user:
        instance.user.delete()

# pour mettre a jour user lors de modification d'un Tiers
@receiver(post_save, sender=Tiers)
def update_user_from_tiers_change(sender, instance, **kwargs):
    """
    Dès qu'un Tiers est modifié, on vérifie s'il est lié à un Employé.
    Si c'est le cas, on met à jour le compte Utilisateur associé.
    """
    try:
        # On vérifie si ce Tiers a un profil employé (via le related_name='profil_employe')
        if hasattr(instance, 'profil_employe'):
            employe = instance.profil_employe
            user = employe.user

            if user:
                # 1. Extraction du nouveau nom d'utilisateur (préfixe email)
                if instance.email and '@' in instance.email:
                    nouveau_username = instance.email.split('@')[0].lower()
                else:
                    nouveau_username = instance.code.lower()

                # 2. Mise à jour des champs de l'utilisateur
                user.username = nouveau_username
                user.email = instance.email
                user.first_name = instance.prenoms
                user.last_name = instance.nom
                user.save()

    except Exception as e:
        # On peut logger l'erreur ici pour ne pas bloquer l'enregistrement du Tiers
        print(f"Erreur lors de la synchronisation utilisateur : {e}")

#signal pour changer mot de passe dans premiere connection
@receiver(models.signals.post_save, sender=User)
def password_changed_callback(sender, instance, **kwargs):
    # Si le mot de passe a été modifié (ceci est simplifié)
    # Dans l'admin, on peut vérifier si l'utilisateur a un profil employé
    if hasattr(instance, 'profil_employe'):
        # Si on est dans la phase de redirection, on pourrait aussi
        # simplement décocher la case manuellement ou via une vue personnalisée.
        pass

@receiver(models.signals.post_save, sender=User)
def set_password_changed_status(sender, instance, **kwargs):
    """
    Dès qu'un utilisateur est sauvegardé (ce qui arrive après un changement de MDP),
    on bascule son statut d'employé.
    """
    if hasattr(instance, 'profil_employe'):
        employe = instance.profil_employe
        # Si l'utilisateur est en train de changer son mot de passe via l'admin
        # On considère que s'il a soumis le formulaire avec succès, il a fini.
        # Note: Dans un système réel, on pourrait vérifier si le mdp a réellement changé.
        if employe.doit_changer_mot_de_passe:
            # On ne passe à False que si l'utilisateur vient de se connecter
            # et qu'il n'est plus à sa "création"
            if instance.last_login is not None:
                employe.doit_changer_mot_de_passe = False
                employe.save()

@receiver(user_logged_in)
def check_first_login(sender, user, request, **kwargs):
    if hasattr(user, 'profil_employe') and user.profil_employe.doit_changer_mot_de_passe:
        from django.contrib import messages
        messages.warning(request, "C'est votre première connexion, piere de changer votre mot de passe.")
        # La redirection se fera via le middleware ou l'admin index décoré plus haut.




#pour gerer les depenses
class Depense(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Motif de la dépense")
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_depense = models.DateField(default=timezone.now, verbose_name="Date effective")
    description = models.TextField(blank=True, null=True, verbose_name="Détails supplémentaires")

    # Liaisons
    employe_responsable = models.ForeignKey(
        'societe.Employe',
        on_delete=models.PROTECT,
        related_name='depenses_gerees',
        verbose_name="Employé responsable"
    )

    # Auditc
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    enregistre_par = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        editable=False,
        related_name='depenses_enregistrees'
    )

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ['-date_depense']

    def __str__(self):
        return f"{self.titre} ({self.montant})"


#pour paiement employer
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PaiementEmploye(models.Model):
    # Liaison avec l'employé qui reçoit le paiement
    employe = models.ForeignKey(
        'societe.Employe',
        on_delete=models.PROTECT,
        related_name='mes_paiements',
        verbose_name="Employé bénéficiaire"
    )

    montant = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Montant payé")
    date_paiement = models.DateField(default=timezone.now, verbose_name="Date du paiement")
    motif = models.CharField(
        max_length=255,
        help_text="Ex: Salaire Mars 2026, Prime, etc.",
        verbose_name="Motif"
    )
    notes = models.TextField(blank=True, null=True)

    # Audit / Traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    enregistre_par = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        editable=False
    )

    class Meta:
        verbose_name = "Paiement Employé"
        verbose_name_plural = "Paiements Employés"
        ordering = ['-date_paiement']

    def __str__(self):
        # On remonte à l'identité via : employe -> tiers -> nom
        try:
            nom_complet = f"{self.employe.tiers.nom.upper()} {self.employe.tiers.prenoms}"
        except AttributeError:
            nom_complet = "Employé inconnu"

        return f"Paiement {nom_complet} - {self.montant}"

