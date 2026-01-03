<script lang="ts">
    import { onMount } from "svelte";
    let code: string;
    let qrCode: string | null = null;

    async function handleTotp() {

        const response = await fetch("https://localhost/api/v1/totp/setup", {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${window.localStorage.getItem("setup_token")}`,
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();

        qrCode = data.qr_code;

        console.log(data);
    }
    onMount(() => {
        handleTotp();
    });

    let verifyTotp = async () => {
        const response = await fetch("https://localhost/api/v1/totp/verify", {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${window.localStorage.getItem("setup_token")}`,
                'Content-Type': 'application/json',
            },
            body: `{"code": "${code}"}`
        });

        if (!response.ok) {
            return;
        }

        const data = await response.json();

        window.localStorage.setItem("access_token", data.access_token);
        window.localStorage.setItem("refresh_token", data.refresh_token);

        window.location.href = "/dashboard";
    }
</script>

<div class="register-container">
    <div class="login-panel">
        <div class="title">
            <h1>SPCloud</h1>
        </div>

        

        <form onsubmit={verifyTotp}>
            {#if qrCode}
                <div class="form-group">
                    <h2>Zeskanuj ten kod z użyciem aplikacji</h2>
                    <img src={qrCode} alt="TOTP QR code" width="100%"/>
                </div>
            {:else}
                <p>Ładowaine kodu QR...</p>
            {/if}  
            
            <div class="form-group">
                <label for="code">Kod:</label>
                <input type="text" id="code" bind:value={code}>
            </div>

            <button type="submit" class="btn-login">Aktywuj</button>
        </form>
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
        color: #fff;
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
