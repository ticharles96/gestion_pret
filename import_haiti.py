import os
import django

# 1. Configuration
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjectBank.settings')
django.setup()

# 2. Import des modèles
from parametres.models import Departement, Ville, Pays

DATA = {
    "Artibonite": ["Gonaïves", "Ennery", "L'Estère", "Poteau", "Saint-Marc", "Verrettes", "La Chapelle",
                   "Petite-Rivière-de-l'Artibonite", "Dessalines", "Desdunes", "Grande-Saline", "Anse-Rouge",
                   "Terre-Neuve", "Marmelade", "Saint-Michel-de-l'Attalaye"],
    "Centre": ["Hinche", "Maïssade", "Thomonde", "Cerca-Cavajal", "Mirebalais", "Saut-d'Eau", "Boucan-Carré",
               "Lascaobas", "Belladère", "Savanette", "Cerca-la-Source", "Thomassique"],
    "Grand'Anse": ["Jérémie", "Abricots", "Bonbon", "Chambellan", "Moron", "Anse-d'Hainault", "Dame-Marie", "Les Irois",
                   "Corail", "Roseaux", "Beaumont", "Pestel", "Îles-Cayemites"],
    "Nippes": ["Miragoâne", "Petite-Rivière-de-Nippes", "Fonds-des-Nègres", "Paillant", "Anse-à-Veau", "Arnaud",
               "L'Asile", "Petit-Trou-de-Nippes", "Plaisance-du-Sud", "Baradères", "Grand-Boucan"],
    "Nord": ["Cap-Haïtien", "Quartier-Morin", "Limonade", "Grande-Rivière-du-Nord", "Bahon", "Saint-Raphaël", "Dondon",
             "Ranquitte", "Pignon", "La Victoire", "Borgne", "Port-Margot", "Limbé", "Bas-Limbé", "Plaisance", "Pilate",
             "Acul-du-Nord", "Plaine-du-Nord", "Milot"],
    "Nord-Est": ["Fort-Liberté", "Ferrier", "Perches", "Ouanaminthe", "Capotille", "Mont-Organisé", "Trou-du-Nord",
                 "Caracol", "Sainte-Suzanne", "Terrier-Rouge", "Vallières", "Carice", "Mombin-Crochu"],
    "Nord-Ouest": ["Port-de-Paix", "Bassin-Bleu", "Chansolme", "Île de la Tortue", "Saint-Louis-du-Nord",
                   "Anse-à-Foleur", "Jean-Rabel", "Môle-Saint-Nicolas", "Baie-de-Henne", "Bombardopolis", "Mare-Rouge"],
    "Ouest": ["Port-au-Prince", "Delmas", "Carrefour", "Pétion-Ville", "Kenscoff", "Gressier", "Léogâne", "Grand-Goâve",
              "Petit-Goâve", "Tabarre", "Cité Soleil", "Arcahaie", "Cabaret", "Croix-des-Bouquets", "Ganthier",
              "Thomazeau", "Cornillon", "Fonds-Verrettes", "Anse-à-Galets", "Pointe-à-Raquette"],
    "Sud": ["Les Cayes", "Camp-Perrin", "Torbeck", "Chantal", "Maniche", "Île-à-Vache", "Port-Salut", "Arniquet",
            "Saint-Jean-du-Sud", "Aquin", "Saint-Louis-du-Sud", "Cavaillon", "Coteaux", "Port-à-Piment",
            "Roche-à-Bateau", "Chardonnières", "Les Anglais", "Tiburon"],
    "Sud-Est": ["Jacmel", "Cayes-Jacmel", "Marigot", "La Vallée-de-Jacmel", "Bainet", "Côtes-de-Fer", "Belle-Anse",
                "Grand-Gosier", "Anse-à-Pitre", "Thiotte"]
}


def run():
    print("--- Démarrage de l'importation ---")

    # On utilise 'nom' au lieu de 'nom_pays'
    haiti_obj, _ = Pays.objects.get_or_create(nom="Haïti")

    for dep_nom, villes in DATA.items():
        # Création ou récupération du département lié à l'objet Haïti
        dep_obj, created = Departement.objects.get_or_create(
            nom=dep_nom,
            defaults={'pays': haiti_obj}
        )

        if created:
            print(f"Département créé : {dep_nom}")

        for ville_nom in villes:
            # Création de la ville
            _, v_created = Ville.objects.get_or_create(
                nom=ville_nom,
                departement=dep_obj
            )
            if v_created:
                print(f"  + Ville ajoutée : {ville_nom}")

    print("\n--- Importation terminée ! ---")


if __name__ == "__main__":
    run()