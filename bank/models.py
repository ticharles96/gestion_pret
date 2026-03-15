from decimal import Decimal
from datetime import timedelta, date
from django.db import models
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
import datetime

from societe.models import Company


# --- MODÈLE CLIENT ---
class Client(models.Model):
    STATUT_DOSSIER = [
        ('INCOMPLET', 'Dossier Incomplet'),
        ('EVALUATION', 'En cours d\'évaluation'),
        ('VALIDE', 'Validé / Éligible'),
        ('BLOQUE', 'Bloqué'),
    ]

    tiers = models.OneToOneField(
        'societe.Tiers', on_delete=models.PROTECT, related_name='profil_client',
        verbose_name="Info Clients", error_messages={'unique': "Ce client possède déjà un compte."}
    )
    statut_dossier = models.CharField(max_length=15, choices=STATUT_DOSSIER, default='INCOMPLET')
    agent_responsable = models.ForeignKey('societe.Employe', on_delete=models.PROTECT, null=True, blank=True)

    montant_pret_actuel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    plafond_pret_max = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_dernier_pret = models.DateField(null=True, blank=True)

    # Finances
    revenus_mensuels = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    depenses_mensuelles = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_update = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False,
                                   related_name='clients_crees')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, editable=False,
                                   related_name='clients_modifier')

    raison_blocage = models.TextField(null=True, blank=True)
    date_blocage = models.DateTimeField(null=True, blank=True, editable=False)

    @property
    def capacite_remboursement(self):
        return self.revenus_mensuels - self.depenses_mensuelles

    def clean(self):
        super().clean()
        if self.statut_dossier == 'BLOQUE' and not self.raison_blocage:
            raise ValidationError({'raison_blocage': "La raison est obligatoire pour un blocage."})
        if not self.agent_responsable:
            raise ValidationError({'agent_responsable': "Un agent responsable est obligatoire."})

    def save(self, *args, **kwargs):
        if self.pk:
            old = Client.objects.get(pk=self.pk)
            if old.statut_dossier != 'BLOQUE' and self.statut_dossier == 'BLOQUE':
                self.date_blocage = timezone.now()
            elif self.statut_dossier != 'BLOQUE':
                self.date_blocage = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tiers.code} - {self.tiers.nom.upper()} {self.tiers.prenoms}"


# --- MODÈLE PRÊT (FUSIONNÉ) ---
class Pret(models.Model):
    CHOIX_FREQUENCE = [('JOUR', 'Journalier'), ('SEMAINE', 'Hebdomadaire'), ('MOIS', 'Mensuel')]
    CHOIX_JOURS = [(i, label) for i, label in
                   enumerate(['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'])]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='prets')
    avaliste = models.ForeignKey(
        'societe.Tiers',  # Remplacez 'societe' par le nom de l'app où se trouve Tiers
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='garanties_donnees',
        verbose_name="Avaliseur / Garant"
    )
    code_pret = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="N° Prêt"
    )
    montant_accorde = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant")
    taux_interet = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_penalite = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    frequence_paiement = models.CharField(max_length=10, choices=CHOIX_FREQUENCE, default='SEMAINE')
    jour_remboursement = models.IntegerField(choices=CHOIX_JOURS, default=0)
    duree = models.IntegerField(default=1)
    date_pret = models.DateField(auto_now_add=True)
    is_solde = models.BooleanField(default=False)
    frais_dossier_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='prets_crees', editable=False)
    modifie_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='prets_modifies',
                                    editable=False)
    agent_responsable = models.ForeignKey(
        'societe.Employe',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False
    )

    def clean(self):
        """
        Règle : Un client ne peut pas avoir deux prêts actifs simultanément.
        """

        super().clean()
        if self.montant_accorde is not None and self.montant_accorde <= 0:
            raise ValidationError({
                'montant_accorde': "Saisir Le montant accordé."
            })

        # 1. Validation individuelle : Empêcher les taux négatifs
        if self.taux_interet < 1:
            raise ValidationError({'taux_interet': "saisir Le taux d'intérêt ."})


        if self.taux_penalite < 1:
            raise ValidationError({'taux_penalite': "Saisir Le taux de pénalité "})

        # On cherche si le client a déjà un prêt où is_solde est False
        # On exclut le prêt actuel lui-même (en cas de modification) avec .exclude(pk=self.pk)
        pret_actif = Pret.objects.filter(
            client=self.client,
            is_solde=False
        ).exclude(pk=self.pk).exists()

        if pret_actif:
            raise ValidationError(
                f"Impossible de créer ce prêt. Le client {self.client} a déjà un prêt en cours non soldé."
            )

    def save(self, *args, **kwargs):

        if not self.code_pret:
            # Génération du code : PRT + ANNÉE + SEQUENCE
            annee = datetime.date.today().year
            dernier_pret = Pret.objects.filter(code_pret__contains=f'PRT-{annee}').order_by('-id').first()

            if dernier_pret:
                # On récupère le dernier numéro et on incrémente
                dernier_numero = int(dernier_pret.code_pret.split('-')[-1])
                nouveau_numero = dernier_numero + 1
            else:
                nouveau_numero = 1

            self.code_pret = f"PRT-{annee}-{nouveau_numero:04d}"
        # 1. On récupère le taux de la compagnie (ex: 3)
        # On ne le fait que si le champ est vide ou si c'est un nouveau prêt
        if self.pk is None or self.frais_dossier_pct is None:
            entreprise = Company.objects.first()
            taux = entreprise.frais_dossier_pct if entreprise else 0

            # 2. ON EFFECTUE L'OPÉRATION ET ON ENREGISTRE DANS frais_dossier_pct
            if self.montant_accorde and taux:
                # Calcul : (Montant Accordé * Taux) / 100
                self.frais_dossier_pct = (self.montant_accorde * taux) / Decimal('100')

        is_new = self.pk is None
        if self.client and self.client.agent_responsable:
            self.agent_responsable = self.client.agent_responsable

        # Sauvegarde finale
        self.full_clean()
        super().save(*args, **kwargs)

        # Mise à jour du client
        if self.client and is_new:
            self.client.date_dernier_pret = timezone.now().date()
            self.client.montant_pret_actuel += self.montant_accorde
            self.client.save(update_fields=['date_dernier_pret', 'montant_pret_actuel'])

    @property
    def total_a_payer(self):
        """Capital + Intérêts initiaux uniquement"""
        m = self.montant_accorde or Decimal('0')
        return m + (m * (self.taux_interet or 0) / Decimal('100'))

    @property
    def montant_echeance(self):
        if self.duree and self.duree > 0:
            return self.total_a_payer / Decimal(str(self.duree))
        return Decimal('0.00')

    @property
    def date_premiere_echeance(self):
        if not self.date_pret: return None
        # On calcule l'écart
        jours = (self.jour_remboursement - self.date_pret.weekday() + 7) % 7

        # Si le jour de remboursement est AUJOURD'HUI, on peut forcer à la semaine prochaine (+7)
        # en changeant le %7 final ou en ajoutant une condition :
        if jours == 0:
            jours = 7

        return self.date_pret + timedelta(days=jours)

    @property
    def date_fin_prevue(self):
        debut = self.date_premiere_echeance
        if not debut or not self.duree: return None
        mult = {'JOUR': 1, 'SEMAINE': 7, 'MOIS': 30}.get(self.frequence_paiement, 7)
        return debut + timedelta(days=(self.duree - 1) * mult)

    @property
    def total_deja_paye(self):
        return self.paiements.aggregate(total=models.Sum('montant_paye'))['total'] or Decimal('0')

    @property
    def montant_penalites_accumulees(self):
        """Calcul informatif des pénalités (non intégrées au solde comptable)"""
        if self.is_solde or self.taux_penalite <= 0 or not self.date_premiere_echeance:
            return Decimal('0.00')

        date_aujourdhui = timezone.now().date()
        #date_aujourdhui = date(2026, 3, 17)

        penalite_totale = Decimal('0.00')
        taux = self.taux_penalite / Decimal('100')
        m_ech = self.montant_echeance
        intervalle = {'JOUR': 1, 'SEMAINE': 7, 'MOIS': 30}.get(self.frequence_paiement, 7)

        for i in range(self.duree):
            date_ech = self.date_premiere_echeance + timedelta(days=i * intervalle)
            if date_aujourdhui > date_ech:
                du_theorique = m_ech * (i + 1)
                # La pénalité s'accumule si le payé total est inférieur au dû théorique à cette date
                if self.total_deja_paye < du_theorique:
                    retard = (date_aujourdhui - date_ech).days
                    penalite_totale += (m_ech * taux) * Decimal(str(retard))
        return penalite_totale

    @property
    def solde_restant(self):
        """
        Calcul comptable REEL : Total à payer - Déjà payé.
        Les pénalités ne sont PAS additionnées ici.
        """
        reste = self.total_a_payer - self.total_deja_paye
        return max(reste, Decimal('0'))

    def __str__(self):
        return f"{self.code_pret} - {self.client.tiers.nom} {self.client.tiers.prenoms}"


# --- MODÈLE PAIEMENT ---
class Paiement(models.Model):
    pret = models.ForeignKey(Pret, on_delete=models.PROTECT, related_name='paiements')
    date_paiement = models.DateTimeField(default=timezone.now)
    montant_paye = models.DecimalField(max_digits=12, decimal_places=2)
    mode_paiement = models.CharField(max_length=50, choices=[('CASH', 'Espèces'), ('MOBILE', 'Mobile paiement')],
                                     default='CASH')
    penalite_payee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Pénalité Versée"
    )

    # --- AJOUTE CES DEUX LIGNES ICI ---
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    # ----------------------------------

    cree_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='paiements_crees',
                                 editable=False)
    modifie_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='paiements_modifies',
                                    editable=False)
    agent_responsable = models.ForeignKey(
        'societe.Employe',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False
    )

    class Meta:
        # Nom utilisé pour les boutons "Ajouter un..."
        verbose_name = "Remboursement"

        # Nom affiché dans le menu de gauche et les titres de listes
        verbose_name_plural = "Remboursements"

    def clean(self):
        # 1. Vérification de sécurité pour éviter le crash "Paiement has no pret"
        if not self.pret_id:
            raise ValidationError({'pret': "Vous devez sélectionner un prêt valide."})

        try:
            # On récupère l'objet prêt une seule fois pour tout le reste
            mon_pret = self.pret

            # --- BLOC PÉNALITÉS (Ton code d'origine) ---
            penalites_dues = mon_pret.montant_penalites_accumulees
            penalites_dues = penalites_dues.quantize(Decimal('0.00'))
            saisie = (self.penalite_payee or Decimal('0.00')).quantize(Decimal('0.00'))

            if penalites_dues > 0:
                if saisie != penalites_dues:
                    raise ValidationError({
                        'penalite_payee': f"Paiement intégral requis. "
                                          f"Saisi : {saisie:.2f} | "
                                          f"Attendu : {penalites_dues:.2f}"
                    })
            elif saisie > 0:

                raise ValidationError({
                    'penalite_payee': "Ce prêt n'a aucune pénalité. Veuillez laisser ce champ à 0.00."
                })

            # --- BLOC ÉCHÉANCE (Ton display echeance) ---
            attendu = mon_pret.montant_echeance
            if round(self.montant_paye, 2) != round(attendu, 2):
                # Utilisation du formatage pour un affichage propre dans l'erreur
                raise ValidationError(f"Montant incorrect. Vous devez payer exactement {attendu:.2f}")

        except ObjectDoesNotExist:
            raise ValidationError({'pret': "Le prêt sélectionné n'existe pas."})

    def save(self, *args, **kwargs):
        # 1. On récupère l'agent avant la sauvegarde
        if self.pret and self.pret.client and self.pret.client.agent_responsable:
            self.agent_responsable = self.pret.client.agent_responsable

        # 2. ON SAUVEGARDE LE PAIEMENT D'ABORD
        # C'est crucial pour que le solde_restant prenne en compte ce montant
        super().save(*args, **kwargs)

        # 3. APRES la sauvegarde, on vérifie si le prêt doit être soldé
        if self.pret:
            # On récupère une instance fraîche du prêt pour avoir le solde à jour
            p = Pret.objects.get(pk=self.pret.pk)

            # Vérification du solde (seuil de 0.01 pour éviter les problèmes de micro-arrondis)
            if p.solde_restant <= 0.01:
                # On met à jour le prêt
                p.is_solde = True
                p.save(update_fields=['is_solde'])

                # On remet le montant actuel du client à 0
                if p.client:
                    client = p.client
                    client.montant_pret_actuel = 0
                    client.save(update_fields=['montant_pret_actuel'])

    def __str__(self):
        return f"Paiement {self.id} - {self.pret.code_pret}"