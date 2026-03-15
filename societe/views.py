from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from .models import Company, Phone
import urllib.parse


def generate_company_info_pdf(request, company_id):
    # 1. Récupérer l'entreprise
    company = get_object_or_404(Company, pk=company_id)

    # 2. Récupérer les téléphones
    repertoire_telephonique = Phone.objects.filter(company=company)

    # 3. Récupérer l'adresse principale
    # .first() permet de ne pas planter si aucune adresse n'est cochée principale
    adresse_principale = company.addresses.filter(is_principal=True).first()

    # 4. Construction du texte du QR Code
    qr_text = f"SOCIETE: {company.name}\n"
    qr_text += f"NIF: {company.tax_id}\n"

    if company.email_contact:
        qr_text += f"EMAIL: {company.email_contact}\n"

    if company.website:
        qr_text += f"WEB: {company.website}\n"

    # Ajout de l'adresse principale si elle existe
    if adresse_principale:
        qr_text += f"ADR: {adresse_principale.ville}, {adresse_principale.full_address}\n"

    # Ajout des téléphones
    if repertoire_telephonique.exists():
        qr_text += "TEL: "
        liste_tel = [f"{p.label}: {p.phone_number}" for p in repertoire_telephonique]
        qr_text += " / ".join(liste_tel)

    # 5. Génération de l'URL du QR Code
    # On utilise une taille de 250x250 car il y a maintenant beaucoup de texte
    encoded_data = urllib.parse.quote(qr_text)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_data}"

    # 6. Contexte et rendu
    template_path = 'pdf/company_profile.html'
    context = {
        'company': company,
        'phones': repertoire_telephonique,
        'qr_code_url': qr_url,
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Fiche_{company.name}.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Erreur lors de la génération du PDF', status=500)

    return response