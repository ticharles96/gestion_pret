import io
import os
import base64
import qrcode
from io import BytesIO

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string

from xhtml2pdf import pisa

# Importations depuis vos applications
from societe.models import Tiers, TiersAdresse, Contact, Company, Phone


def tiers_pdf_view(request, pk):
    # 1. Récupération des données de base
    obj = get_object_or_404(Tiers, pk=pk)
    company = Company.objects.first()

    # 2. Récupération de TOUS les téléphones de l'entreprise
    company_phones = []
    if company:
        company_phones = company.phones.all()

    # 3. Dossier d'identité du Tiers
    identity = getattr(obj, 'identity_docs', None)

    # 4. Relations du Tiers (Adresses et Contacts)
    adresses_qs = TiersAdresse.objects.filter(tiers=obj).order_by('-est_principale')
    contacts_qs = Contact.objects.filter(tiers=obj).order_by('-est_principal')

    # 5. Génération du QR Code
    qr_data = f"ID: {obj.code}\nNOM: {obj.nom}\nCOMPANY: {company.name if company else 'N/A'}"
    qr = qrcode.make(qr_data)
    qr_buffer = BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    # 6. Contexte complet
    context = {
        'obj': obj,
        'company': company,
        'company_phones': company_phones,
        'identity': identity,
        'adresses': adresses_qs,
        'contacts': contacts_qs,
        'qr_code': qr_base64,
    }

    # 7. Rendu et conversion PDF
    html_string = render_to_string('admin/pdf_tiers.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Fiche_{obj.code}.pdf"'

    pisa_status = pisa.CreatePDF(
        BytesIO(html_string.encode("UTF-8")),
        dest=response,
        encoding='UTF-8'
    )

    if pisa_status.err:
        return HttpResponse("Erreur lors de la génération du PDF", status=500)

    return response