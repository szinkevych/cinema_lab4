(function () {
    "use strict";

    var emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    var usernamePattern = /^[A-Za-z0-9_.-]{3,30}$/;
    var phonePattern = /^\+?[0-9]{10,15}$/;

    function validateField(field) {
        field.setCustomValidity("");
        if (field.disabled || field.type === "hidden") return;

        var value = field.value;
        var trimmed = value.trim();
        var name = field.name;

        if (field.required && !trimmed) {
            field.setCustomValidity("Заповніть це поле.");
        } else if (field.maxLength > 0 && value.length > field.maxLength) {
            field.setCustomValidity("Максимум " + field.maxLength + " символів.");
        } else if (name === "username" && trimmed && !usernamePattern.test(trimmed)) {
            field.setCustomValidity("Логін: 3-30 символів, латинські літери, цифри та . _ -.");
        } else if (field.type === "email" && trimmed && !emailPattern.test(trimmed)) {
            field.setCustomValidity("Введіть коректну адресу електронної пошти.");
        } else if (name === "phone" && trimmed &&
                   !phonePattern.test(trimmed.replace(/[\s\-()]/g, ""))) {
            field.setCustomValidity("Телефон має містити від 10 до 15 цифр; дозволено початковий +.");
        } else if (name === "password" && field.form.dataset.validatePassword === "true" && value &&
                   (value.length < 8 || value.length > 128 ||
                    !/[^\W\d_]/u.test(value) || !/\d/.test(value))) {
            field.setCustomValidity("Пароль має містити 8-128 символів, літери й цифри.");
        } else if (name === "base_price" && trimmed &&
                   !/^(?:\d+|\d+[.,]\d{1,2}|[.,]\d{1,2})$/.test(trimmed)) {
            field.setCustomValidity("Вкажіть суму числом, не більше двох знаків після коми.");
        } else if (name === "release_year" && trimmed &&
                   Number(value) > new Date().getFullYear() + 5) {
            field.setCustomValidity("Рік випуску не може бути більш ніж на 5 років у майбутньому.");
        } else if (field.type === "number" && trimmed) {
            var number = Number(value);
            if (!Number.isFinite(number)) {
                field.setCustomValidity("Введіть коректне число.");
            } else if (field.min !== "" && number < Number(field.min)) {
                field.setCustomValidity("Значення не може бути меншим за " + field.min + ".");
            } else if (field.max !== "" && number > Number(field.max)) {
                field.setCustomValidity("Значення не може бути більшим за " + field.max + ".");
            }
        } else if (name === "start_time" && trimmed &&
                   new Date(value) <= new Date()) {
            field.setCustomValidity("Початок сеансу має бути в майбутньому.");
        }
    }

    function validateForm(form) {
        var valid = true;
        Array.prototype.forEach.call(form.elements, function (field) {
            if (field.willValidate) {
                validateField(field);
                if (!field.validity.valid) valid = false;
            }
        });

        var password = form.elements.password;
        var password2 = form.elements.password2;
        if (password && password2 && password2.value && password.value !== password2.value) {
            password2.setCustomValidity("Паролі не збігаються.");
            valid = false;
        }

        var from = form.elements.from;
        var to = form.elements.to;
        if (from && to && from.value && to.value && from.value > to.value) {
            to.setCustomValidity("Кінець періоду не може бути раніше за початок.");
            valid = false;
        }

        var seats = form.querySelectorAll('input[name="seats"]:checked:not(:disabled)');
        if (form.id === "sell-form") {
            var maxSeats = Number(form.dataset.max);
            if (!seats.length) {
                var firstSeat = form.querySelector('input[name="seats"]:not(:disabled)');
                if (firstSeat) firstSeat.setCustomValidity("Оберіть хоча б одне місце.");
                valid = false;
            } else if (seats.length > maxSeats) {
                seats[0].setCustomValidity("В одному замовленні не більше " + maxSeats + " місць.");
                valid = false;
            }
        }

        return valid;
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form").forEach(function (form) {
            form.addEventListener("input", function (event) {
                if (event.target.willValidate) validateField(event.target);
                if (event.target.name === "password" || event.target.name === "password2") {
                    var confirmation = form.elements.password2;
                    if (confirmation && confirmation.value) {
                        confirmation.setCustomValidity(
                            form.elements.password.value === confirmation.value ? "" : "Паролі не збігаються."
                        );
                    }
                }
            });
            form.addEventListener("change", function (event) {
                if (event.target.willValidate) validateField(event.target);
            });
            form.addEventListener("submit", function (event) {
                if (!validateForm(form)) {
                    event.preventDefault();
                    form.reportValidity();
                }
            });
            form.noValidate = true;
        });
    });
})();
