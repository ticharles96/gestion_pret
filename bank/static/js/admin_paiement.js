// admin_paiement.js
document.addEventListener('DOMContentLoaded', function() {
    const pretSelect = document.getElementById('id_pret');
    const dateInput = document.getElementById('id_date_paiement_0');
    const timeInput = document.getElementById('id_date_paiement_1');

    if (pretSelect) {
        pretSelect.addEventListener('change', function() {
            const pretId = this.value;
            if (!pretId) return;

            // On vide les champs temporairement pour montrer que ça charge
            if (dateInput) dateInput.value = "";

            fetch(`/admin/bank/paiement/get-next-date/?pret_id=${pretId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // On utilise un timeout de 50ms pour être sûr que
                        // l'auto-remplissage de Django ne repasse pas par dessus
                        setTimeout(() => {
                            dateInput.value = data.next_date;
                            timeInput.value = data.next_time;
                            console.log("Date injectée :", data.next_date);
                        }, 50);
                    }
                });
        });
    }
});