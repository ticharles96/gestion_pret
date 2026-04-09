document.addEventListener('DOMContentLoaded', function () {
    const deptSelect = document.querySelector('#id_departement');
    const villeSelect = document.querySelector('#id_ville');

    deptSelect.addEventListener('change', function () {
        const url = "/ajax/load-villes/?departement_id=" + this.value;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                villeSelect.innerHTML = '<option value="">---------</option>';
                data.forEach(function (ville) {
                    const option = new Option(ville.nom, ville.id);
                    villeSelect.add(option);
                });
            });
    });
});