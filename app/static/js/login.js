// app/static/js/login.js
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const submitBtn = document.getElementById('submitBtn');

    let isEmailValid = false;
    let isPasswordValid = false;

    // Validation en temps réel
    emailInput.addEventListener('input', validateEmail);
    passwordInput.addEventListener('input', validatePassword);

    form.addEventListener('submit', function (e) {
        if (!isEmailValid || !isPasswordValid) {
            e.preventDefault();
            return false;
        }
    });

    function validateEmail() {
        const email = emailInput.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (email === '') {
            showError(emailInput, emailError, "L'email est requis.");
            isEmailValid = false;
        } else if (!emailRegex.test(email)) {
            showError(emailInput, emailError, 'Email invalide (ex: nom@domaine.ne).');
            isEmailValid = false;
        } else {
            clearError(emailInput, emailError);
            isEmailValid = true;
        }
        updateSubmitButton();
        return isEmailValid;
    }

    function validatePassword() {
        const password = passwordInput.value;

        if (password === '') {
            showError(passwordInput, passwordError, 'Le mot de passe est requis.');
            isPasswordValid = false;
        } else if (password.length < 3) {
            showError(passwordInput, passwordError, '8 caractères minimum.');
            isPasswordValid = false;
        } else {
            clearError(passwordInput, passwordError);
            isPasswordValid = true;
        }
        updateSubmitButton();
        return isPasswordValid;
    }

    function showError(input, errorDiv, message) {
        input.classList.remove('is-valid');
        input.classList.add('is-invalid');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    function clearError(input, errorDiv) {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
    }

    function updateSubmitButton() {
        submitBtn.disabled = !(isEmailValid && isPasswordValid);
    }

    // Initialisation
    submitBtn.disabled = true;
    validateEmail();
    validatePassword();
});