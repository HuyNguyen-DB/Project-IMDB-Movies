document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-submit-on-change]").forEach(function (element) {
        element.addEventListener("change", function () {
            element.form.submit();
        });
    });
});
