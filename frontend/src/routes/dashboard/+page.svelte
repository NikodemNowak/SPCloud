<script lang="ts">
    import feather from '$lib/assets/feather-sprite.svg';
    import logoUrl from '$lib/assets/logo.svg';
    import FuzzySearch from 'fuzzy-search';
    import StorageProgress from '../../components/storage-progress.svelte';
    import {onMount} from 'svelte';

    type FileDesc = {
        id: number;
        name: string;
        is_favorite: boolean;
        date: Date;
        size: number;
    };

    let activeNavLink = $state('my-files');
    let search = $state('');
    let isSortMenuOpen = $state(false);
    let sortBy = $state('name');
    let sortOrder = $state('asc');
    let isDeleteConfirming = $state(false);

    let indeterminateCheckbox: HTMLInputElement;

    let selectedFileIds = $state<number[]>([]);
    let result = $state<FileDesc[]>([]);
    let files = $state<FileDesc[]>([]);
    let isDownloading = $state(false);
    let downloadingText = $state('');

    const MAX_STORAGE_MB = 100;
    const usedStorageMB = $derived(
        files.reduce((sum, file) => sum + (file.size / (1024 * 1024)), 0)
    );

    const searcher = $derived(new FuzzySearch(Array.from(files), ['name'], {
        caseSensitive: false
    }));


    let refresh_access_token = async () => {
        let response = await fetch('http://localhost:8000/api/v1/users/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                "refresh_token": localStorage.getItem('refresh_token')
            })
        });

        if (response.ok) {
            let data = await response.json();

            if (data.access_token) {
                localStorage.setItem('access_token', data.access_token);
            }
        } else {
            localStorage.clear();
            window.location.href = '/login';
        }
    }

    setInterval(refresh_access_token, 600000);


    const displayedFiles = $derived(files
        .filter((file) => {
            if (search.length > 0) {
                return result.some((res) => file.id === res.id);
            }
            if (activeNavLink === 'favorites') {
                return file.is_favorite;
            }
            if (activeNavLink === 'recent') {
                const now = Date.now();
                const oneWeekInMs = 7 * 24 * 60 * 60 * 1000;
                return file.date.getTime() >= (now - oneWeekInMs);
            }
            return true;
        })
        .sort((a, b) => {
            let comparison: number = 0;
            if (sortBy === 'name') {
                const nameA = a.name || '';
                const nameB = b.name || '';
                comparison = nameA.localeCompare(nameB, undefined, {numeric: true});
            } else if (sortBy === 'date') {
                comparison = a.date.getTime() - b.date.getTime();
            } else if (sortBy === 'size') {
                comparison = a.size - b.size;
            }
            return sortOrder === 'asc' ? comparison : -comparison;
        }));

    const areAllDisplayedSelected = $derived(
        displayedFiles.length > 0 && selectedFileIds.length === displayedFiles.length
    );
    const areSomeDisplayedSelected = $derived(selectedFileIds.length > 0 && !areAllDisplayedSelected);

    $effect(() => {
        if (indeterminateCheckbox) {
            indeterminateCheckbox.indeterminate = areSomeDisplayedSelected;
        }
    });

    function handleSortChange(newSortBy: string, newSortOrder: string) {
        sortBy = newSortBy;
        sortOrder = newSortOrder;
        isSortMenuOpen = false;
    }

    function toggleFavorite(fileId: number) {
        const file = files.find((f) => f.id === fileId);
        if (!file) return;

        const newFavoriteStatus = !file.is_favorite;

        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        fetch('http://localhost:8000/api/v1/files/change-is-favorite', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_id: fileId,
                is_favorite: newFavoriteStatus
            }),
        }).then((response) => {
            if (response.status === 401 || response.status === 403) {
                console.error('Token nieprawidłowy - przekierowanie na /login');
                window.localStorage.removeItem('access_token');
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error('Failed to change favorite status');
            }
            return response.json();
        }).then((data) => {
            if (data) {
                console.log('Status ulubionego zmieniony pomyślnie:', data);
                file.is_favorite = newFavoriteStatus;
                files = [...files];
            }
        }).catch((error) => {
            console.error('Błąd podczas zmiany statusu ulubionego:', error);
        });
    }

    function toggleSelectAll() {
        if (areAllDisplayedSelected) {
            selectedFileIds = [];
        } else {
            selectedFileIds = displayedFiles.map((f) => f.id);
        }
    }

    async function handleDownload() {
        console.log('Pobieranie plików o ID:', selectedFileIds);

        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        if (selectedFileIds.length < 1) {
            console.error("Nie wybrano plików");
            return;
        }

        isDownloading = true;
        downloadingText = '';

        const dotsInterval = setInterval(() => {
            downloadingText = downloadingText.length >= 3 ? '' : downloadingText + '.';
        }, 500);

        try {
            if (selectedFileIds.length === 1) {
                const fileId = selectedFileIds[0];
                const file = files.find((f) => f.id === fileId);

                const response = await fetch(`http://localhost:8000/api/v1/files/download/${fileId}`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                });

                if (response.status === 401 || response.status === 403) {
                    console.error('Token nieprawidłowy - przekierowanie na /login');
                    window.localStorage.removeItem('access_token');
                    window.location.href = '/login';
                    clearInterval(dotsInterval);
                    isDownloading = false;
                    return;
                }

                if (!response.ok) {
                    throw new Error('Download failed');
                }

                const blob = await response.blob();
                if (blob) {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = file?.name || 'plik';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    console.log('Plik pobrany pomyślnie');
                }
            } else {
                let fileIds = selectedFileIds.map(value => value);
                console.log(JSON.stringify(fileIds));
                let result = await fetch('http://localhost:8000/api/v1/files/download', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        file_ids: fileIds
                    })
                });

                let blob = await result.blob();

                if (blob) {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'download.zip';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    console.log('Plik pobrany pomyślnie');
                }
            }
        } catch (error) {
            console.error('Błąd podczas pobierania pliku:', error);
        } finally {
            clearInterval(dotsInterval);
            downloadingText = ' zakończone';
            selectedFileIds = [];
            setTimeout(() => {
                isDownloading = false;
            }, 1000);
        }
    }

    function handleDelete() {
        if (!isDeleteConfirming) {
            isDeleteConfirming = true;
            return;
        }

        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        const deletePromises = selectedFileIds.map((fileId) => {
            return fetch(`http://localhost:8000/api/v1/files/${fileId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            }).then((response) => {
                if (response.status === 401 || response.status === 403) {
                    console.error('Token nieprawidłowy - przekierowanie na /login');
                    window.localStorage.removeItem('access_token');
                    window.location.href = '/login';
                    return;
                }

                if (!response.ok) {
                    return response.json().then((data) => {
                        console.error('Błąd podczas usuwania pliku:', data.detail || data);
                    });
                }
            }).catch((error) => {
                console.error('Błąd podczas usuwania pliku:', error);
            });
        });

        Promise.all(deletePromises).then(() => {
            fetchFiles();
            selectedFileIds = [];
            isDeleteConfirming = false;
        });
    }

    function cancelDelete() {
        isDeleteConfirming = false;
    }

    function handleLogout() {
        console.log('Wylogowywanie...');
        window.localStorage.removeItem('access_token');
        window.location.href = '/login';
    }

    function handleSearch() {
        result = searcher.search(search);
    }

    function fetchFiles() {
        const token = window.localStorage.getItem('access_token');

        fetch("http://localhost:8000/api/v1/files/", {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        }).then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch files');
            }
            return response.json();
        }).then((data) => {
            console.log('Pobrano pliki:', data);

            files = data.files.map((file: any) => ({
                id: file.id,
                name: file.name || 'Nieznany plik',
                is_favorite: file.is_favorite || false,
                date: new Date(file.updated_at.replace('Z', '')),
                size: file.size || 0
            }));
        }).catch((error) => {
            console.error('Błąd podczas pobierania plików:', error);
        });
    }

    function handleFileUpload(event: Event) {
        const input = event.target as HTMLInputElement;
        const files = input.files;

        if (!files || files.length === 0) {
            console.error('Nie wybrano plików');
            return;
        }

        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        const fileArray = Array.from(files);

        async function uploadFilesSequentially() {
            for (const file of fileArray) {
                const formData = new FormData();
                formData.append('file', file);

                await fetch("http://localhost:8000/api/v1/files/upload", {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                    body: formData,
                }).then((response) => {
                    if (!response.ok) {
                        throw new Error('Upload failed');
                    }
                    return response.json();
                }).then((data) => {
                    console.log('Plik przesłany pomyślnie:', data);
                }).catch((error) => {
                    console.error('Błąd podczas przesyłania pliku:', error);
                });
            }

            input.value = '';
            fetchFiles();
        }

        uploadFilesSequentially();
    }

    onMount(() => {
        refresh_access_token();
        fetchFiles();
    });

    function formatBytes(bytes: number, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
</script>

<div class="background-container">
    <div class="dashboard-panel">
        <nav class="sidebar">
            <div>
                <div class="logo">
                    <img alt="Logo" height="32" src={logoUrl} width="32"/>
                    <span class="logo-text">SPCloud</span>
                </div>
                <ul class="nav-links">
                    <li class:active={activeNavLink === 'my-files'}>
                        <button onclick={() => (activeNavLink = 'my-files')}>
                            <svg class="feather">
                                <use href="{feather}#hard-drive"/>
                            </svg>
                            <span class="link-text">Moje pliki</span>
                        </button>
                    </li>
                    <li class:active={activeNavLink === 'favorites'}>
                        <button onclick={() => (activeNavLink = 'favorites')}>
                            <svg class="feather">
                                <use href="{feather}#star"/>
                            </svg>
                            <span class="link-text">Ulubione</span>
                        </button>
                    </li>
                    <li class:active={activeNavLink === 'recent'}>
                        <button onclick={() => (activeNavLink = 'recent')}>
                            <svg class="feather">
                                <use href="{feather}#clock"/>
                            </svg>
                            <span class="link-text">Najnowsze</span>
                        </button>
                    </li>
                </ul>
            </div>
            <div>
                <StorageProgress usedStorage={usedStorageMB}
                                 maxStorage={MAX_STORAGE_MB}/>
                <div class="upload">

                    <label for="upload" class="upload-button">
                        <svg class="feather">
                            <use href="{feather}#upload-cloud"/>
                        </svg>
                        <div class="upload-label-text">
                            Prześlij plik
                        </div>
                    </label>
                    <input type="file" id="upload" multiple
                           onchange={handleFileUpload}/>
                </div>
            </div>
        </nav>

        <div class="main-content">
            <header class="top-bar">
                <div class="search-bar">
                    <svg class="feather search-icon">
                        <use href="{feather}#search"/>
                    </svg>
                    <input placeholder="Search" type="text" bind:value={search}
                           oninput={handleSearch}/>
                </div>
                <div class="top-bar-actions">
                    <div class="sort-menu">
                        <button class="sort-button"
                                onclick={() => (isSortMenuOpen = !isSortMenuOpen)}>
                            <svg class="feather">
                                <use href="{feather}#sliders"/>
                            </svg>
                            <span>Sortuj</span>
                        </button>

                        {#if isSortMenuOpen}
                            <ul class="sort-dropdown">
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('name', 'asc')}
                                    >
                                        Nazwa
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-up"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'name' && sortOrder === 'asc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('name', 'desc')}
                                    >
                                        Nazwa
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-down"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'name' && sortOrder === 'desc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('date', 'asc')}
                                    >
                                        Data
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-up"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'date' && sortOrder === 'asc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('date', 'desc')}
                                    >
                                        Data
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-down"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'date' && sortOrder === 'desc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('size', 'asc')}
                                    >
                                        Rozmiar
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-up"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'size' && sortOrder === 'asc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                                <li class="sortable-header">
                                    <button
                                            type="button"
                                            class="sort-btn"
                                            onclick={() => handleSortChange('size', 'desc')}
                                    >
                                        Rozmiar
                                        <svg class="feather sort-arrow">
                                            <use href="{feather}#arrow-down"/>
                                        </svg>
                                    </button>
                                    {#if sortBy === 'size' && sortOrder === 'desc'}
                                        <svg class="feather check-icon">
                                            <use href="{feather}#check"/>
                                        </svg>
                                    {/if}
                                </li>
                            </ul>
                        {/if}
                    </div>
                    <button class="logout-button" onclick={handleLogout}
                            title="Wyloguj się">
                        <svg class="feather">
                            <use href="{feather}#log-out"/>
                        </svg>
                    </button>
                </div>
            </header>

            <main class="file-list-container">
                <div class="file-list-header">
                    <div class="header-left">
                        <input
                                type="checkbox"
                                class="input-checkbox"
                                onclick={toggleSelectAll}
                                checked={areAllDisplayedSelected}
                                bind:this={indeterminateCheckbox}
                        />
                        <h2>Lista plików</h2>
                    </div>
                    <div class="header-right">
                        <div class="header-columns">
                            <span class="header-date">Data modyfikacji</span>
                            <span class="header-size">Rozmiar</span>
                        </div>
                    </div>
                </div>
                <ul class="file-list">
                    {#each displayedFiles as file (file.id)}
                        <li class="file-item">
                            <input
                                    type="checkbox"
                                    bind:group={selectedFileIds}
                                    value={file.id}
                                    name={file.id.toString()}
                                    id={file.id.toString()}
                                    class="input-checkbox"
                            />
                            <button
                                    aria-label="favorite button"
                                    class="favorite-btn"
                                    class:favorited={file.is_favorite}
                                    onclick={() => toggleFavorite(file.id)}
                            >
                                <svg class="feather star-icon">
                                    <use href="{feather}#star"/>
                                </svg>
                            </button>
                            <svg class="feather file">
                                <use href="{feather}#file"/>
                            </svg>
                            <span class="file-name">{file.name}</span>
                            <span class="file-date">{file.date.toLocaleDateString('pl-PL', {
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit'
                            })}</span>
                            <span class="file-size">{formatBytes(file.size)}</span>
                        </li>
                    {/each}
                </ul>
            </main>

            {#if selectedFileIds.length > 0}
                <div class="download-bar">
                    <button class="download-button" onclick={handleDownload}
                            disabled={isDownloading}>
                        <svg class="feather">
                            <use href="{feather}#download"/>
                        </svg>
                        {#if isDownloading}
                            Pobieranie{downloadingText}
                        {:else if selectedFileIds.length === 1}
                            Pobierz
                        {:else}
                            Pobierz wiele plików
                        {/if}
                    </button>
                </div>

                <div class="delete-bar">
                    {#if !isDeleteConfirming}
                        <button class="delete-button" onclick={handleDelete}>
                            <svg class="feather">
                                <use href="{feather}#trash-2"/>
                            </svg>
                            Usuń
                        </button>
                    {:else}
                        <div class="delete-confirm">
                            <span class="delete-text">Czy na pewno?</span>
                            <button class="confirm-yes" onclick={handleDelete}
                                    title="Tak, usuń">
                                <svg class="feather">
                                    <use href="{feather}#check"/>
                                </svg>
                            </button>
                            <button class="confirm-no" onclick={cancelDelete}
                                    title="Nie, anuluj">
                                <svg class="feather">
                                    <use href="{feather}#x"/>
                                </svg>
                            </button>
                        </div>
                    {/if}
                </div>
            {/if}
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

    .upload-button {
        display: flex;
        flex-direction: row;
    }

    .upload-label-text {
        padding-left: 1rem;
    }

    .feather {
        width: 24px;
        height: 24px;
        stroke: var(--text-primary);
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
    }

    input[type='file'] {
        display: none;
    }

    .upload {
        cursor: pointer;
    }

    .feather.file {
        margin-right: 8px;
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

    .upload {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 12px 16px;
        border-radius: 8px;
        text-decoration: none;
        color: var(--text-secondary);
        font-weight: 500;
        transition: all 0.2s ease;
        background-color: transparent;
        border: none;
        cursor: pointer;
    }

    .upload label {
        cursor: pointer;
    }

    .upload:hover {
        background-color: var(--hover-bg);
        color: #fff;
    }

    .upload:hover svg {
        color: #fff;
    }

    .sort-menu {
        position: relative;
    }

    .sort-dropdown {
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        background-color: var(--dropdown-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        list-style: none;
        padding: 8px;
        width: 200px;
        z-index: 1000;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
    }

    .sort-btn {
        all: unset;
        display: flex;
        align-items: center;
        cursor: pointer;
        width: 100%;
    }

    .sort-arrow {
        width: 16px;
        height: 16px;
        margin-left: 6px;
    }

    .sort-dropdown li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-radius: 6px;
        cursor: pointer;
        color: var(--text-secondary);
        font-weight: 500;
    }

    .sort-dropdown li:hover {
        background-color: var(--hover-bg);
    }

    .sort-dropdown .check-icon {
        width: 18px;
        height: 18px;
        stroke: var(--primary-purple);
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: 18px;
    }

    .file-list-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        position: relative;
        z-index: 20;
        gap: 12px;
    }

    .header-right {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .header-columns {
        display: flex;
        gap: 12px;
        flex-shrink: 0;
    }

    .header-date,
    .header-size {
        font-size: 0.75rem;
        color: var(--text-secondary);
        text-align: center;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .header-date {
        width: 130px;
    }

    .header-size {
        width: 125px;
    }

    .file-date,
    .file-size {
        font-size: 0.875rem;
        color: var(--text-secondary);
        white-space: nowrap;
        text-align: center;
        padding: 0 12px;
    }

    .file-date {
        width: 150px;
    }

    .file-size {
        width: 100px;
    }

    .favorite-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 24px;
        width: 0;
        opacity: 0;
        overflow: hidden;
        transition: width 0.2s ease,
        opacity 0.2s ease;
        margin-right: 0;
    }

    .file-item:hover .favorite-btn,
    .favorite-btn.favorited {
        width: 24px;
        opacity: 1;
        margin-right: 12px;
    }

    .star-icon {
        width: 18px;
        height: 18px;
        stroke: var(--text-secondary);
        transition: all 0.2s ease;
        flex-shrink: 0;
    }

    .favorite-btn:hover .star-icon {
        stroke: var(--star-color-hover);
    }

    .favorite-btn.favorited .star-icon {
        fill: var(--star-color-selected);
        stroke: var(--star-color-selected);
    }

    .sort-button {
        display: flex;
        align-items: center;
        gap: 8px;
        color: var(--text-secondary);
        font-weight: 500;
        padding: 12px 16px;
        border-radius: 8px;
        transition: all 0.2s ease;
        background-color: transparent;
        border: none;
        white-space: nowrap;
    }

    .sort-button:hover {
        background-color: var(--hover-bg);
        color: #fff;
    }

    .sort-button:hover svg {
        stroke: #fff;
    }

    .sort-button svg {
        width: 18px;
        height: 18px;
    }

    button {
        all: unset;
        display: inline-block;
        cursor: pointer;
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
        color: var(--text-secondary);
        transition: color 0.2s ease;
    }

    .nav-links li button {
        all: unset;
        width: 100%;
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 12px 16px;
        border-radius: 8px;
        text-decoration: none;
        color: var(--text-secondary);
        font-weight: 500;
        transition: all 0.2s ease;
        cursor: pointer;
        box-sizing: border-box;
    }

    .nav-links li button:hover {
        background-color: var(--hover-bg);
    }

    .nav-links li.active button {
        background-color: var(--active-selection-bg);
        color: #fff;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .nav-links li.active button svg,
    .nav-links li button:hover svg {
        color: #fff;
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
        gap: 12px;
    }

    .top-bar-actions {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
    }

    .search-bar {
        position: relative;
        flex: 1;
        min-width: 200px;
        max-width: none;
    }

    .search-bar .search-icon {
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        color: var(--text-secondary);
    }

    .search-bar input {
        width: 100%;
        padding: 10px 14px 10px 42px;
        background-color: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        font-size: 1rem;
        font-family: var(--font-family), sans-serif;
    }

    .search-bar input::placeholder {
        color: var(--text-secondary);
    }

    .search-bar input:focus {
        outline: none;
        border-color: var(--primary-purple);
        box-shadow: 0 0 0 3px rgba(157, 115, 255, 0.3);
    }

    .logout-button {
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
        flex-shrink: 0;
    }

    .logout-button:hover {
        background-color: var(--hover-bg);
    }

    .file-list-container {
        flex-grow: 1;
        padding: 24px;
        overflow-y: auto;
    }

    .file-list-container h2 {
        font-size: 1.5rem;
        font-weight: 600;
    }

    .file-list {
        list-style-type: none;
        overflow-x: auto;
    }

    .file-item {
        display: grid;
        grid-template-columns: auto auto auto 1fr 150px 100px;
        align-items: center;
        padding: 12px 16px;
        border-radius: 8px;
        transition: background-color 0.2s ease;
        cursor: pointer;
        gap: 12px;
    }

    .file-name {
        flex-grow: 1;
    }

    .file-date,
    .file-size {
        font-size: 0.875rem;
        color: var(--text-secondary);
        white-space: nowrap;
        text-align: center;
    }

    .file-date {
        width: 150px;
    }

    .file-size {
        width: 100px;
    }

    .file-item:hover {
        background-color: var(--hover-bg);
    }

    .input-checkbox {
        -webkit-appearance: none;
        appearance: none;
        background-color: transparent;
        margin: 0;
        font: inherit;
        color: currentColor;

        width: 18px;
        height: 18px;
        border: 2px solid var(--text-secondary);
        border-radius: 4px;
        /* margin-right: 18px; */
        flex-shrink: 0;
        cursor: pointer;

        display: grid;
        place-content: center;
        transition: all 0.15s ease-in-out;
    }

    .input-checkbox::before {
        content: '';
        width: 10px;
        height: 10px;
        transform: scale(0);
        transition: 120ms transform ease-in-out;
        box-shadow: inset 1em 1em #fff;

        clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
    }

    .input-checkbox:checked {
        background-color: var(--primary-purple);
        border-color: var(--primary-purple);
    }

    .input-checkbox:checked::before {
        transform: scale(1);
    }

    .input-checkbox:focus-visible {
        outline: 2px solid var(--primary-purple);
        outline-offset: 2px;
    }

    .download-bar {
        position: absolute;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        animation: slide-up 0.3s ease-out forwards;
    }

    .download-button {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 24px;
        background-color: var(--primary-purple);
        color: #fff;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        transition: background-color 0.2s ease,
        width 0.3s ease-out;
        white-space: nowrap;
    }

    .download-button:hover {
        background-color: #a77bff;
    }

    .download-button .feather {
        stroke: #fff;
    }

    .delete-bar {
        position: absolute;
        bottom: 24px;
        right: 24px;
        animation: slide-up-right 0.3s ease-out forwards;
    }

    .delete-button,
    .delete-confirm {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 24px;
        color: #fff;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        transition: background-color 0.2s ease,
        width 0.3s ease-out;
        white-space: nowrap;
        background-color: #dc2626;
    }

    .delete-button:hover,
    .delete-confirm:hover {
        background-color: #b91c1c;
    }

    .delete-button .feather {
        stroke: #fff;
    }

    .delete-text {
        color: #fff;
        font-weight: 600;
        font-size: 1rem;
        white-space: nowrap;
    }

    .confirm-yes,
    .confirm-no {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        transition: all 0.2s ease;
    }

    .confirm-yes {
        background-color: rgba(255, 255, 255, 0.2);
    }

    .confirm-yes:hover {
        background-color: rgba(255, 255, 255, 0.3);
    }

    .confirm-no {
        background-color: rgba(255, 255, 255, 0.2);
    }

    .confirm-no:hover {
        background-color: rgba(255, 255, 255, 0.3);
    }

    .confirm-yes .feather,
    .confirm-no .feather {
        stroke: #fff;
        width: 16px;
        height: 16px;
    }

    @keyframes expand-confirm {
        from {
            opacity: 0;
            width: 48px;
        }
        to {
            opacity: 1;
            width: auto;
        }
    }

    @keyframes slide-up {
        from {
            opacity: 0;
            transform: translate(-50%, 20px);
        }
        to {
            opacity: 1;
            transform: translate(-50%, 0);
        }
    }

    @keyframes slide-up-right {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @media (max-width: 1200px) {
        .sidebar {
            width: 88px;
            padding: 24px 16px;
            transition: width 0.3s ease;
        }

        .upload svg {
            width: 28px;
            height: 28px;
        }

        .main-content {
            width: calc(100% - 88px);
            transition: width 0.3s ease;
        }

        .logo {
            justify-content: center;
        }

        .logo-text,
        .upload-label-text,
        .link-text {
            display: none;
        }

        .nav-links li button {
            justify-content: center;
        }

        .upload {
            justify-content: center;
        }

        .header-columns {
            display: flex;
            margin-left: 20px;
        }

        .file-item {
            grid-template-columns: auto auto auto 1fr 150px 80px;
        }

        .file-date,
        .file-size {
            display: block;
        }
    }

    @media (max-width: 768px) {
        .dashboard-panel {
            height: 100vh;
            width: 100vw;
            border-radius: 0;
            padding: 0;
        }

        .background-container {
            padding: 0;
        }

        .top-bar {
            padding: 12px 16px;
            gap: 8px;
        }

        .search-bar {
            flex: 1;
            min-width: 150px;
            max-width: none;
        }

        .top-bar-actions {
            gap: 8px;
        }

        .sort-button span {
            display: none;
        }

        .sort-button {
            padding: 8px;
            min-width: 40px;
            justify-content: center;
        }

        .logout-button {
            width: 40px;
            height: 40px;
            padding: 8px;
        }

        .file-list-container {
            padding: 16px;
            overflow-x: auto;
        }

        .file-list {
            min-width: 800px;
        }

        .file-list-header {
            flex-direction: row;
            align-items: center;
            min-width: 800px;
        }

        .file-list-header h2 {
            font-size: 1.2rem;
        }

        .header-right {
            width: auto;
        }

        .header-columns {
            display: flex;
            margin-right: 30px;
        }

        .file-item {
            grid-template-columns: auto auto auto 1fr 150px 80px;
            gap: 12px;
            padding: 12px 16px;
            min-width: 800px;
        }

        .file-date,
        .file-size {
            display: block;
        }
    }
</style>
