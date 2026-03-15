import os
import base64
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import get_object_or_404
from django.utils import timezone
from xhtml2pdf import pisa
import qrcode  # Assurez-vous d'avoir installé : pip install qrcode

from societe.models import Company
from .models import Client

def client_render_pdf_view(request, client_id):
    # 1. Récupération des données
    client = get_object_or_404(Client, pk=client_id)
    company = Company.objects.first()

    # 2. Génération du QR Code (ID du client)
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(f"CLIENT-ID: {client.tiers.code} {client.tiers.nom} {client.tiers.prenoms}")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    buffered = BytesIO()
    img_qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    # 3. Chemin du Logo (si défini dans Company ou static)
    # On cherche d'abord si la Company a un logo, sinon on peut mettre un chemin fixe
    logo_path = None
    if company and company.logo:
        logo_path = company.logo.path

    # 4. Préparation du contexte complet
    context = {
        'client': client,
        'company': company,
        'currency': str(company.currency) if company and company.currency else "HTG",
        'qr_code': qr_base64,
        'logo_path': logo_path,
        'now': timezone.now(),
        'request': request,  # Permet d'accéder à request.user dans le template
    }

    # 5. Création du PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Fiche_{client.tiers.code}.pdf"'

    template = get_template('admin/client_pdf_template.html')
    html = template.render(context)

    # Conversion
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f'Erreur PDF: <pre>{html}</pre>')
    return response


#pour le contrat
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Pret
from django.utils import timezone

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Pret
from django.utils import timezone


def imprimer_contrat_pret(request, pret_id):
    # 1. Récupération du prêt et des entités liées
    pret = get_object_or_404(Pret, id=pret_id)
    tiers = pret.client.tiers
    avaliste = pret.avaliste

    # 2. Récupération des informations de l'entreprise (Company)
    entreprise = Company.objects.first()

    # 3. Récupération de l'adresse principale du tiers
    adresse_obj = tiers.adresses.filter(est_principale=True).first()
    if not adresse_obj:
        adresse_obj = tiers.adresses.first()

    # 4. Récupération du document d'identité (OneToOneField)
    identite = getattr(tiers, 'identity_docs', None)

    # 5. Récupération des CONTACTS (Téléphones)
    # On tente de récupérer via le related_name 'contacts'
    # Sinon on utilise le suffixe par défaut '_set'
    if hasattr(tiers, 'contacts'):
        liste_contacts = tiers.contacts.all()
    elif hasattr(tiers, 'tierscontact_set'):
        liste_contacts = tiers.tierscontact_set.all()
    else:
        liste_contacts = []

    # 6. Préparation du contexte pour le template
    context = {
        'pret': pret,
        'tiers': tiers,
        'avaliste': avaliste,
        'entreprise': entreprise,
        'identite': identite,
        'adresse_principale': adresse_obj,
        'contacts': liste_contacts,  # Cette variable contient la liste des numéros
        'date_impression': timezone.now(),
    }

    # 7. Création de la réponse PDF
    pdf_response = HttpResponse(content_type='application/pdf')
    pdf_response['Content-Disposition'] = f'inline; filename="Contrat_{pret.code_pret}.pdf"'

    # 8. Rendu du template
    template = get_template('bank/pdf_contrat_pret.html')
    html = template.render(context)

    # 9. Génération du PDF
    pisa_status = pisa.CreatePDF(html, dest=pdf_response)

    # 10. Vérification d'erreur
    if pisa_status.err:
        return HttpResponse("Erreur lors de la génération du PDF", status=500)

    return pdf_response