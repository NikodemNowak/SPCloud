<script lang="ts">
    import feather from '$lib/assets/feather-sprite.svg';
    import logoUrl from '$lib/assets/logo.svg';
    import { onMount } from 'svelte';

    let limit = $state(100);
    let isDownloading = $state(false);
    let downloadingText = $state('');

    function handleLogout() {
        console.log('Wylogowywanie...');
        window.localStorage.removeItem('access_token');
        window.location.href = '/login';
    }

    async function handleDownloadLogs() {
        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        isDownloading = true;
        downloadingText = '';
        const dotsInterval = setInterval(() => {
            downloadingText = downloadingText.length >= 3 ? '' : downloadingText + '.';
        }, 500);

        try {
            const response = await fetch(`https://localhost/api/v1/logs/download/${limit}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (response.status === 401 || response.status === 403) {
                console.error('Brak uprawnień lub token nieprawidłowy');
                window.location.href = '/login'; // Or dashboard if just 403?
                return;
            }

            if (!response.ok) {
                throw new Error('Log download failed');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'logs.txt';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch.length === 2)
                    filename = filenameMatch[1];
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            console.log('Logi pobrane pomyślnie');

        } catch (error) {
            console.error('Błąd podczas pobierania logów:', error);
            alert('Wystąpił błąd podczas pobierania logów.');
        } finally {
            clearInterval(dotsInterval);
            isDownloading = false;
        }
    }
</script>

<div class="background-container">
    <div class="dashboard-panel">
        <nav class="sidebar">
            <div>
                <div class="logo">
                    <img alt="Logo" height="32" src={logoUrl} width="32"/>
                    <span class="logo-text">SPCloud Admin</span>
                </div>
                <ul class="nav-links">
                    <li>
                        <a href="/dashboard">
                            <svg class="feather">
                                <use href="{feather}#arrow-left"/>
                            </svg>
                            <span class="link-text">Wróć do plików</span>
                        </a>
                    </li>
                     <li class="active">
                        <button>
                            <svg class="feather">
                                <use href="{feather}#file-text"/>
                            </svg>
                            <span class="link-text">Logi systemowe</span>
                        </button>
                    </li>
                </ul>
            </div>
        </nav>

        <div class="main-content">
            <header class="top-bar">
                <h2>Panel Administratora - Logi</h2>
                <div class="top-bar-actions">
                    <button class="logout-button" onclick={handleLogout} title="Wyloguj się">
                        <svg class="feather">
                            <use href="{feather}#log-out"/>
                        </svg>
                    </button>
                </div>
            </header>

            <main class="content-container">
                <div class="logs-control-panel">
                    <h3>Pobieranie logów systemowych</h3>
                    <p class="description">
                        Pobierz ostatnie logi systemowe. Możesz określić liczbę ostatnich wpisów do pobrania.
                    </p>

                    <div class="form-group">
                        <label for="limit">Liczba wpisów (limit):</label>
                        <input
                                type="number"
                                id="limit"
                                bind:value={limit}
                                min="1"
                                max="10000"
                        />
                    </div>

                    <button class="download-button" onclick={handleDownloadLogs} disabled={isDownloading}>
                        <svg class="feather">
                            <use href="{feather}#download"/>
                        </svg>
                        {#if isDownloading}
                            Pobieranie{downloadingText}
                        {:else}
                            Pobierz logi
                        {/if}
                    </button>
                </div>
            </main>
        </div>
    </div>
</div>

<style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
        color: var(--text-primary);
    }

    :global(body) {
        font-family: var(--font-family), sans-serif;
        overflow: hidden;
    }

    .background-container {
        width: 100vw;
        height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 40px;
    }

    .dashboard-panel {
        width: 100%;
        height: 90vh;
        min-height: 600px;
        background: var(--primary-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        box-shadow: 0 8px 32px 0 rgba(14, 11, 32, 0.37);
        display: flex;
        overflow: hidden;
    }

    .sidebar {
        width: 240px;
        background: var(--sidebar-bg);
        padding: 24px;
        border-right: 1px solid var(--border-color);
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .logo {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 40px;
    }

    .logo-text {
        font-size: 1.1rem;
        font-weight: 600;
        color: #fff;
    }

    .nav-links {
        list-style: none;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    .nav-links svg {
        width: 24px;
        height: 24px;
        stroke: var(--text-secondary);
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
        margin-right: 12px;
        transition: color 0.2s ease;
    }

    .nav-links li a,
    .nav-links li button {
        all: unset;
        width: 100%;
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-radius: 8px;
        text-decoration: none;
        color: var(--text-secondary);
        font-weight: 500;
        transition: all 0.2s ease;
        cursor: pointer;
        box-sizing: border-box;
    }

    .nav-links li a:hover,
    .nav-links li button:hover {
        background-color: var(--hover-bg);
    }

    .nav-links li.active button {
        background-color: var(--active-selection-bg);
        color: #fff;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .nav-links li.active button svg,
    .nav-links li button:hover svg,
    .nav-links li a:hover svg {
        color: #fff;
        stroke: #fff;
    }

    .main-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        width: calc(100% - 240px);
        position: relative;
    }

    .top-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 24px;
        border-bottom: 1px solid var(--border-color);
        flex-shrink: 0;
    }

    .top-bar h2 {
        font-size: 1.5rem;
        font-weight: 600;
    }

    .logout-button {
        all: unset;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        cursor: pointer;
        color: var(--text-secondary);
        padding: 8px;
        border-radius: 50%;
        transition: all 0.2s ease;
        box-sizing: border-box;
    }

    .logout-button svg {
        width: 24px;
        height: 24px;
        stroke: currentColor;
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
    }

    .logout-button:hover {
        background-color: var(--hover-bg);
        color: #fff;
    }

    .content-container {
        flex-grow: 1;
        padding: 40px;
        overflow-y: auto;
        display: flex;
        justify-content: center;
        align-items: start;
    }

    .logs-control-panel {
        background-color: rgba(0, 0, 0, 0.2);
        padding: 30px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        max-width: 500px;
        width: 100%;
    }

    .logs-control-panel h3 {
        margin-bottom: 16px;
        color: #fff;
    }

    .description {
        margin-bottom: 24px;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    .form-group {
        margin-bottom: 24px;
    }

    .form-group label {
        display: block;
        margin-bottom: 8px;
        color: var(--text-primary);
        font-weight: 500;
    }

    .form-group input {
        width: 100%;
        padding: 12px;
        background-color: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        color: #fff;
        font-size: 1rem;
    }

    .form-group input:focus {
        outline: none;
        border-color: var(--primary-purple);
    }

    .download-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        width: 100%;
        padding: 14px;
        background-color: var(--primary-purple);
        color: #fff;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }

    .download-button:hover:not(:disabled) {
        background-color: #a77bff;
    }

    .download-button:disabled {
        opacity: 0.7;
        cursor: not-allowed;
    }

    .download-button svg {
        width: 20px;
        height: 20px;
        stroke: #fff;
        stroke-width: 2;
        fill: none;
    }
</style>
