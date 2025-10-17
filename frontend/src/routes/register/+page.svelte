<script lang="ts">
    let username = '';
    let password = '';
    let repeatPassword = '';

    let registerFailedUsernameTaken = false;
    let registerFailedUsernameIsEmpty = false;

    let registerFailedPasswordsNotSame = false;
    let registerFailedPasswordIsEmpty = false;
    let registerFailedPasswordTooShort = false;

    /**
     * Handles the login process when the "Login" button is clicked.
     */
    function handleRegister() {

        const MIN_PASSWORD_LENGTH = 2;

        registerFailedUsernameTaken = false;
        registerFailedUsernameIsEmpty = false;
        registerFailedPasswordsNotSame = false;
        registerFailedPasswordIsEmpty = false;
        registerFailedPasswordTooShort = false;

        if (username.length === 0) {
            registerFailedUsernameIsEmpty = true;
            console.error('Username is empty');
            return;
        }

        if (password.length === 0) {
            registerFailedPasswordIsEmpty = true;
            console.error('Password is empty');
            return;
        }

        if (password !== repeatPassword) {
            registerFailedPasswordsNotSame = true;
            console.error('Passwords do not match');
            return;
        }

        if (password.length < MIN_PASSWORD_LENGTH) {
            registerFailedPasswordTooShort = true;
            console.error('Password is too short');
            return;
        }

        fetch("http://localhost:8000/api/v1/users/register", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        }).then((response) => {
            return response.json();
        }).then((data) => {
            console.log('Success:', data);
            window.localStorage.setItem('token', JSON.stringify(data.access_token));
            window.location.href = '/dashboard';
        }).catch((error) => {
            registerFailedUsernameTaken = true;
            console.error('Error:', error);
        })
    }
</script>

<div class="register-container">
    <div class="login-panel">
        <div class="title">
            <h1>SPCloud</h1>
        </div>

        <form onsubmit={handleRegister}>
            <div class="form-group">
                <label for="username">Login</label>
                <input
                        type="text"
                        id="username"
                        bind:value={username}
                        placeholder="Wprowadź login"
                        required
                />
            </div>

            <div class="form-group">
                <label for="password">Hasło</label>
                <input
                        type="password"
                        id="password"
                        bind:value={password}
                        placeholder="Wprowadź hasło"
                        required
                />
            </div>

            <div class="form-group">
                <label for="repeat-password">Powtórz hasło</label>
                <input
                        type="password"
                        id="repeat-password"
                        bind:value={repeatPassword}
                        placeholder="Wprowadź hasło"
                        required
                />
            </div>

            <button type="submit" class="btn-login">Zarejestruj się</button>
        </form>
        {#if registerFailedUsernameTaken}
            <div class="error">Ten login jest już użyty!</div>
        {:else if registerFailedUsernameIsEmpty}
            <div class="error">Login nie może być pusty!</div>
        {:else if registerFailedPasswordIsEmpty}
            <div class="error">Hasło nie może być puste!</div>
        {:else if registerFailedPasswordsNotSame}
            <div class="error">Hasła nie są takie same!</div>
        {:else if registerFailedPasswordTooShort}
            <div class="error">Hasło jest za krótkie!</div>
        {/if}

        <div class="register-section">
            <a href="/login" class="btn-register"> Zaloguj się </a>
        </div>
    </div>
</div>

<style>
    .register-container {
        width: 100%;
        min-height: 100dvh;
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 0;
        padding: 0;
        overflow-x: hidden;
        position: relative;
    }

    .login-panel {
        width: 100%;
        max-width: 400px;
        background: var(--primary-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        box-shadow: 0 8px 32px 0 rgba(14, 11, 32, 0.37);
        padding: 40px;
        animation: slideIn 0.5s ease-out;
        box-sizing: border-box;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-50px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    .title {
        text-align: center;
        margin-bottom: 40px;
    }

    .title h1 {
        color: #fff;
        font-size: 28px;
        font-weight: 600;
        margin: 0;
    }

    .form-group {
        margin-bottom: 20px;
    }

    .form-group label {
        display: block;
        color: var(--text-secondary);
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 8px;
    }

    .form-group input {
        width: 100%;
        padding: 12px 15px;
        background-color: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        font-size: 1rem;
        font-family: var(--font-family), serif;
        color: var(--text-primary);
        box-sizing: border-box;
    }

    .form-group input:focus {
        outline: none;
        border-color: var(--primary-purple);
        box-shadow: 0 0 0 3px rgba(157, 115, 255, 0.3);
    }

    .btn-login {
        width: 100%;
        padding: 14px;
        background: var(--primary-purple);
        color: white;
        border: none;
        border-radius: 10px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-top: 10px;
    }

    .btn-login:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(157, 115, 255, 0.4);
    }

    .btn-login:active {
        transform: translateY(0);
    }

    .register-section {
        margin-top: 30px;
        padding-top: 20px;
        border-top: 1px solid var(--border-color);
        text-align: center;
    }

    .btn-register {
        text-decoration: none;
        background: transparent;
        color: var(--primary-purple);
        border: 2px solid var(--primary-purple);
        padding: 12px 30px;
        border-radius: 10px;
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .btn-register:hover {
        background: var(--primary-purple);
        color: white;
        transform: translateY(-2px);
    }

    .btn-register:active {
        transform: translateY(0);
    }

    .error {
        color: red;
        text-align: center;
        padding: 2px;
    }

    @media (max-width: 768px) {
        .register-container {
            padding: 15px;
            justify-content: center;
            align-items: center;
            min-height: 100dvh;
            background-attachment: scroll;
            background-size: cover;
            background-position: center center;
        }

        .login-panel {
            max-width: 100%;
            width: 100%;
            padding: 25px 18px;
            max-height: none;
            border-radius: 12px;
            margin: 0;
            box-sizing: border-box;
        }

        .title {
            margin-bottom: 25px;
        }

        .title h1 {
            font-size: 24px;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-group label {
            font-size: 13px;
            margin-bottom: 6px;
        }

        .form-group input {
            padding: 12px 14px;
            font-size: 16px;
        }

        .btn-login {
            padding: 13px;
            font-size: 15px;
            margin-top: 8px;
        }

        .register-section {
            margin-top: 20px;
            padding-top: 16px;
        }

        .btn-register {
            padding: 11px 25px;
            font-size: 14px;
            display: inline-block;
        }

        .error {
            font-size: 14px;
            margin-top: 12px;
        }
    }

    @media (min-width: 769px) and (max-width: 1199px) {
        .register-container {
            justify-content: center;
            padding: 20px;
        }
    }

    @media (min-width: 1200px) {
        .register-container {
            justify-content: center;
        }
    }
</style>
