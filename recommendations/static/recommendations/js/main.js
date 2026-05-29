// =========================================================
// 1. SUBMIT FORM ON CHANGE
// - Dùng cho các select/filter có data-submit-on-change
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-submit-on-change]").forEach(function (element) {
        element.addEventListener("change", function () {
            element.form.submit();
        });
    });
});


// =========================================================
// 2. DATE / DATETIME INPUT PLACEHOLDER CONTROL
// - Tự thêm class has-value khi input date/datetime đã có giá trị
// - Giúp placeholder tiếng Việt tự ẩn sau khi người dùng chọn ngày/giờ
// =========================================================

document.addEventListener("DOMContentLoaded", function () {
    const dateInputs = document.querySelectorAll(".date-input, .datetime-input");

    dateInputs.forEach(function (input) {
        const wrapper = input.closest(".date-input-wrapper, .datetime-input-wrapper");

        if (!wrapper) {
            return;
        }

        function updateState() {
            if (input.value) {
                wrapper.classList.add("has-value");
            } else {
                wrapper.classList.remove("has-value");
            }
        }

        updateState();

        input.addEventListener("input", updateState);
        input.addEventListener("change", updateState);
        input.addEventListener("blur", updateState);
    });
});