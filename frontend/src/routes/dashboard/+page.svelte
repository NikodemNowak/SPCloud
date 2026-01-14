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

    type FileVersion = {
        version_number: number;
        size: number;
        created_at: string;
        created_by: string;
        is_current: boolean;
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
    let isAdmin = $state(false);

    // Upload progress state
    let isUploading = $state(false);
    let uploadProgress = $state(0);
    let uploadFileName = $state('');
    let uploadCurrentFile = $state(0);
    let uploadTotalFiles = $state(0);
    let uploadError = $state('');

    let isVersionsOpen = $state(false);
    let versionsLoading = $state(false);
    let versionsError = $state('');
    let selectedFileForVersions = $state<FileDesc | null>(null);
    let fileVersions = $state<FileVersion[]>([]);

    const apiErrorTranslations: Record<string, string> = {
        'Uploading this file would exceed your storage quota.': 'Przesłanie tego pliku przekroczyłoby limit miejsca.',
        'File with the same name already exists in the database.': 'Plik o tej nazwie już istnieje.',
        'Invalid UUID format': 'Nieprawidłowy identyfikator pliku.',
        'User not found': 'Nie znaleziono użytkownika.',
        "File not found or you don't have permission to access it": 'Nie znaleziono pliku lub brak uprawnień.',
        "File not found or you don't have permission to delete it": 'Nie znaleziono pliku lub brak uprawnień do usunięcia.',
        "File not found or you don't have permission to modify it": 'Nie znaleziono pliku lub brak uprawnień do modyfikacji.',
        'Cannot delete current version. Restore another version first.': 'Nie można usunąć aktualnej wersji. Najpierw przywróć inną.'
    };

    function getErrorDetail(source: XMLHttpRequest | string | null): string | null {
        if (!source) {
            return null;
        }

        const responseText = typeof source === 'string' ? source : source.responseText;
        if (!responseText) {
            return null;
        }

        try {
            const parsed = JSON.parse(responseText);
            if (typeof parsed?.detail === 'string') {
                return parsed.detail;
            }
        } catch {
            return null;
        }

        return null;
    }

    function localizeApiError(detail: string | null, status: number): string {
        if (detail && apiErrorTranslations[detail]) {
            return apiErrorTranslations[detail];
        }

        if (detail && /Version\s+\d+\s+not\s+found/i.test(detail)) {
            return 'Nie znaleziono wskazanej wersji pliku.';
        }

        if (status === 413) {
            return 'Przekroczono limit miejsca na dysku.';
        }

        if (status === 409) {
            return 'Plik o tej nazwie już istnieje.';
        }

        if (status === 400) {
            return 'Nieprawidłowe dane przesyłanego pliku.';
        }

        if (status >= 500) {
            return 'Błąd serwera. Spróbuj ponownie później.';
        }

        return 'Nie udało się przesłać pliku.';
    }

    function buildVersionedFilename(name: string, version: number): string {
        const lastDot = name.lastIndexOf('.');
        if (lastDot === -1) {
            return `${name}_v${version}`;
        }
        const base = name.slice(0, lastDot);
        const ext = name.slice(lastDot);
        return `${base}_v${version}${ext}`;
    }

    // Download progress state
    let downloadProgress = $state(0);
    let downloadFileName = $state('');

    let isVersionDownloading = $state(false);
    let versionDownloadProgress = $state(0);
    let versionDownloadLabel = $state('');

    let usedStorageMB = $state(0);
    let maxStorageMB = $state(100);

    const searcher = $derived(new FuzzySearch(Array.from(files), ['name'], {
        caseSensitive: false
    }));


    let refresh_access_token = async () => {
        let response = await fetch('https://localhost/api/v1/users/refresh', {
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

    async function checkAdminStatus() {
        const token = window.localStorage.getItem('access_token');
        if (!token) return;

        try {
            const response = await fetch('https://localhost/api/v1/users/isadmin', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (response.ok) {
                isAdmin = await response.json();
            }
        } catch (error) {
            console.error('Error checking admin status:', error);
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

        fetch('https://localhost/api/v1/files/change-is-favorite', {
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
        downloadProgress = 0;

        function downloadWithProgress(url: string, method: string, body: string | null, fileName: string): Promise<void> {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open(method, url, true);
                xhr.setRequestHeader('Authorization', `Bearer ${token}`);
                if (body) {
                    xhr.setRequestHeader('Content-Type', 'application/json');
                }
                xhr.responseType = 'blob';

                xhr.onprogress = (event) => {
                    if (event.lengthComputable) {
                        downloadProgress = Math.round((event.loaded / event.total) * 100);
                        console.log(`Download progress: ${downloadProgress}%`);
                    } else if (event.loaded) {
                        // If total is unknown, show bytes downloaded
                        console.log(`Downloaded: ${event.loaded} bytes`);
                    }
                };

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        const blob = xhr.response;
                        if (blob) {
                            const downloadUrl = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = downloadUrl;
                            a.download = fileName;
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(downloadUrl);
                            document.body.removeChild(a);
                            console.log('Plik pobrany pomyślnie');
                        }
                        resolve();
                    } else if (xhr.status === 401 || xhr.status === 403) {
                        console.error('Token nieprawidłowy - przekierowanie na /login');
                        window.localStorage.removeItem('access_token');
                        window.location.href = '/login';
                        reject(new Error('Unauthorized'));
                    } else {
                        reject(new Error(`Download failed: ${xhr.statusText}`));
                    }
                };

                xhr.onerror = () => {
                    console.error('Błąd sieci podczas pobierania pliku');
                    reject(new Error('Network error'));
                };

                xhr.send(body);
            });
        }

        try {
            if (selectedFileIds.length === 1) {
                const fileId = selectedFileIds[0];
                const file = files.find((f) => f.id === fileId);
                downloadFileName = file?.name || 'plik';

                await downloadWithProgress(
                    `https://localhost/api/v1/files/download/${fileId}`,
                    'GET',
                    null,
                    downloadFileName
                );
            } else {
                downloadFileName = 'download.zip';
                const fileIds = selectedFileIds.map(value => value);

                await downloadWithProgress(
                    'https://localhost/api/v1/files/download',
                    'POST',
                    JSON.stringify({ file_ids: fileIds }),
                    downloadFileName
                );
            }
        } catch (error) {
            console.error('Błąd podczas pobierania pliku:', error);
        } finally {
            selectedFileIds = [];
            downloadProgress = 100;
            setTimeout(() => {
                isDownloading = false;
                downloadProgress = 0;
                downloadFileName = '';
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
            return fetch(`https://localhost/api/v1/files/${fileId}`, {
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

        fetch("https://localhost/api/v1/files/", {
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
        }).finally(() => {
            fetchStorageInfo();
        });
    }

    async function fetchStorageInfo() {
        const token = window.localStorage.getItem('access_token');
        if (!token) {
            return;
        }

        try {
            const response = await fetch('https://localhost/api/v1/files/me', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();
            usedStorageMB = data.used_storage_mb ?? usedStorageMB;
            maxStorageMB = data.max_storage_mb ?? maxStorageMB;
        } catch (error) {
            console.error('Błąd podczas pobierania informacji o storage:', error);
        }
    }

    function handleFileUpload(event: Event) {
        const input = event.target as HTMLInputElement;
        const uploadFiles = input.files;

        if (!uploadFiles || uploadFiles.length === 0) {
            console.error('Nie wybrano plików');
            return;
        }

        const token = window.localStorage.getItem('access_token');

        if (!token) {
            console.error('Brak tokena - przekierowanie na /login');
            window.location.href = '/login';
            return;
        }

        const fileArray = Array.from(uploadFiles);
        uploadTotalFiles = fileArray.length;
        uploadCurrentFile = 0;
        isUploading = true;
        uploadProgress = 0;

        function uploadFileWithProgress(file: File): Promise<void> {
            return new Promise((resolve, reject) => {
                const formData = new FormData();
                formData.append('file', file);

                const xhr = new XMLHttpRequest();
                xhr.open('POST', 'https://localhost/api/v1/files/upload', true);
                xhr.setRequestHeader('Authorization', `Bearer ${token}`);

                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                        uploadProgress = Math.round((event.loaded / event.total) * 100);
                        console.log(`Upload progress for ${file.name}: ${uploadProgress}%`);
                    }
                };

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        console.log('Plik przesłany pomyślnie:', file.name);
                        resolve();
                    } else if (xhr.status === 401 || xhr.status === 403) {
                        console.error('Token nieprawidłowy - przekierowanie na /login');
                        window.localStorage.removeItem('access_token');
                        window.location.href = '/login';
                        reject(new Error('Unauthorized'));
                    } else {
                        const detail = getErrorDetail(xhr);
                        const localized = localizeApiError(detail, xhr.status);
                        console.error('Błąd podczas przesyłania pliku:', detail || xhr.statusText);
                        uploadError = `${file.name}: ${localized}`;
                        reject(new Error(localized));
                    }
                };

                xhr.onerror = () => {
                    console.error('Błąd sieci podczas przesyłania pliku');
                    reject(new Error('Network error'));
                };

                xhr.send(formData);
            });
        }

        async function uploadFilesSequentially() {
            uploadError = ''; // Reset błędu na początku
            
            for (const file of fileArray) {
                uploadCurrentFile++;
                uploadFileName = file.name;
                uploadProgress = 0;

                try {
                    await uploadFileWithProgress(file);
                } catch (error) {
                    console.error('Błąd podczas przesyłania pliku:', error);
                    // Błąd jest już ustawiony w uploadError, kontynuuj z pozostałymi plikami
                }
            }

            input.value = '';
            
            // Jeśli był błąd, pokaż go przez chwilę przed zamknięciem
            if (uploadError) {
                uploadProgress = 0;
                uploadFileName = '';
                // Poczekaj 4 sekundy przed ukryciem, żeby użytkownik zobaczył błąd
                setTimeout(() => {
                    isUploading = false;
                    uploadError = '';
                }, 4000);
            } else {
                isUploading = false;
                uploadProgress = 0;
                uploadFileName = '';
            }
            
            fetchFiles();
        }

        uploadFilesSequentially();
    }

    onMount(() => {
        refresh_access_token();
        fetchFiles();
        checkAdminStatus();
    });

    async function openVersions(file: FileDesc) {
        selectedFileForVersions = file;
        isVersionsOpen = true;
        versionsError = '';
        versionsLoading = true;
        fileVersions = [];

        const token = window.localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/login';
            return;
        }

        try {
            const response = await fetch(`https://localhost/api/v1/files/${file.id}/versions`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const detail = getErrorDetail(await response.text());
                const localized = localizeApiError(detail, response.status);
                versionsError = localized;
                return;
            }

            const data = await response.json();
            fileVersions = data.versions || [];
        } catch (error) {
            versionsError = 'Nie udało się pobrać wersji pliku.';
        } finally {
            versionsLoading = false;
        }
    }

    function closeVersions() {
        isVersionsOpen = false;
        selectedFileForVersions = null;
        versionsError = '';
        fileVersions = [];
    }

    async function downloadVersion(file: FileDesc, version: number) {
        const token = window.localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/login';
            return;
        }

        versionsError = '';
        isVersionDownloading = true;
        versionDownloadProgress = 0;
        versionDownloadLabel = `${file.name} (v${version})`;

        return new Promise<void>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', `https://localhost/api/v1/files/${file.id}/versions/${version}`, true);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            xhr.responseType = 'blob';

            xhr.onprogress = (event) => {
                if (event.lengthComputable) {
                    versionDownloadProgress = Math.round((event.loaded / event.total) * 100);
                }
            };

            xhr.onload = () => {
                isVersionDownloading = false;
                if (xhr.status >= 200 && xhr.status < 300) {
                    const blob = xhr.response;
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = buildVersionedFilename(file.name, version);
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(downloadUrl);
                    document.body.removeChild(a);
                    resolve();
                } else {
                    const detail = getErrorDetail(xhr);
                    versionsError = localizeApiError(detail, xhr.status);
                    reject(new Error(versionsError));
                }
            };

            xhr.onerror = () => {
                isVersionDownloading = false;
                versionsError = 'Błąd sieci podczas pobierania wersji.';
                reject(new Error(versionsError));
            };

            xhr.send();
        });
    }

    async function restoreVersion(file: FileDesc, version: number) {
        const token = window.localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/login';
            return;
        }

        try {
            const response = await fetch(`https://localhost/api/v1/files/${file.id}/restore/${version}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const detail = getErrorDetail(await response.text());
                versionsError = localizeApiError(detail, response.status);
                return;
            }

            await fetchFiles();
            await openVersions(file);
        } catch (error) {
            versionsError = 'Nie udało się przywrócić wersji.';
        }
    }

    async function deleteVersion(file: FileDesc, version: number) {
        const token = window.localStorage.getItem('access_token');
        if (!token) {
            window.location.href = '/login';
            return;
        }

        try {
            const response = await fetch(`https://localhost/api/v1/files/${file.id}/versions/${version}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const detail = getErrorDetail(await response.text());
                versionsError = localizeApiError(detail, response.status);
                return;
            }

            await fetchFiles();
            await openVersions(file);
        } catch (error) {
            versionsError = 'Nie udało się usunąć wersji.';
        }
    }

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
                    {#if isAdmin}
                        <li>
                            <a href="/admin/logs" class="admin-link">
                                <button>
                                    <svg class="feather">
                                        <use href="{feather}#shield"/>
                                    </svg>
                                    <span class="link-text">Panel Admina</span>
                                </button>
                            </a>
                        </li>
                    {/if}
                </ul>
            </div>
            <div>
                <StorageProgress usedStorage={usedStorageMB}
                                 maxStorage={maxStorageMB}/>
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
                            <span class="header-actions">Wersje</span>
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
                            <button class="versions-btn" title="Wersje" onclick={() => openVersions(file)}>
                                <svg class="feather">
                                    <use href="{feather}#layers"/>
                                </svg>
                            </button>
                        </li>
                    {/each}
                </ul>
            </main>

            {#if isVersionsOpen && selectedFileForVersions}
                <div class="versions-overlay" onclick={closeVersions}>
                    <div class="versions-modal" onclick={(event) => event.stopPropagation()}>
                        <div class="versions-header">
                            <div>
                                <h3>Wersje pliku</h3>
                                <span class="versions-subtitle">{selectedFileForVersions.name}</span>
                            </div>
                            <button class="versions-close" onclick={closeVersions} aria-label="Zamknij">
                                <svg class="feather">
                                    <use href="{feather}#x"/>
                                </svg>
                            </button>
                        </div>

                        {#if versionsLoading}
                            <div class="versions-state">Ładowanie wersji...</div>
                        {:else if versionsError}
                            <div class="versions-state versions-error">{versionsError}</div>
                        {:else if fileVersions.length === 0}
                            <div class="versions-state">Brak zapisanych wersji.</div>
                        {:else}
                            <ul class="versions-list">
                                {#each fileVersions as version}
                                    <li class="version-item" class:is-current={version.is_current}>
                                        <div class="version-main">
                                            <div class="version-badge">
                                                v{version.version_number}
                                                {#if version.is_current}
                                                    <span class="version-current">Aktualna</span>
                                                {/if}
                                            </div>
                                            <div class="version-meta">
                                                <span>{new Date(version.created_at).toLocaleString('pl-PL')}</span>
                                                <span>{formatBytes(version.size)}</span>
                                                <span>Autor: {version.created_by}</span>
                                            </div>
                                        </div>
                                        <div class="version-actions">
                                            <button class="version-action" onclick={() => downloadVersion(selectedFileForVersions, version.version_number)}>
                                                <svg class="feather">
                                                    <use href="{feather}#download"/>
                                                </svg>
                                                Pobierz
                                            </button>
                                            <button class="version-action" disabled={version.is_current}
                                                    onclick={() => restoreVersion(selectedFileForVersions, version.version_number)}>
                                                <svg class="feather">
                                                    <use href="{feather}#rotate-ccw"/>
                                                </svg>
                                                Przywróć
                                            </button>
                                            <button class="version-action danger" disabled={version.is_current}
                                                    onclick={() => deleteVersion(selectedFileForVersions, version.version_number)}>
                                                <svg class="feather">
                                                    <use href="{feather}#trash-2"/>
                                                </svg>
                                                Usuń
                                            </button>
                                        </div>
                                    </li>
                                {/each}
                            </ul>
                        {/if}

                        {#if isVersionDownloading}
                            <div class="versions-progress">
                                <div class="versions-progress-text">
                                    Pobieranie: {versionDownloadLabel}
                                </div>
                                <div class="progress-bar-container">
                                    <div class="progress-bar" style="width: {versionDownloadProgress}%"></div>
                                </div>
                                <div class="versions-progress-percent">{versionDownloadProgress}%</div>
                            </div>
                        {/if}
                    </div>
                </div>
            {/if}

            {#if selectedFileIds.length > 0}
                <div class="download-bar">
                    <button class="download-button" onclick={handleDownload}
                            disabled={isDownloading}>
                        <svg class="feather">
                            <use href="{feather}#download"/>
                        </svg>
                        {#if isDownloading}
                            <span class="download-text">
                                Pobieranie {downloadFileName} ({downloadProgress}%)
                            </span>
                            <div class="progress-bar-container">
                                <div class="progress-bar" style="width: {downloadProgress}%"></div>
                            </div>
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

            {#if isUploading}
                <div class="upload-progress-bar" class:upload-error={uploadError}>
                    <div class="upload-progress-content">
                        <svg class="feather">
                            {#if uploadError}
                                <use href="{feather}#alert-circle"/>
                            {:else}
                                <use href="{feather}#upload-cloud"/>
                            {/if}
                        </svg>
                        <div class="upload-progress-info">
                            {#if uploadError}
                                <span class="upload-error-text">{uploadError}</span>
                            {:else}
                                <span class="upload-progress-text">
                                    Przesyłanie ({uploadCurrentFile}/{uploadTotalFiles}): {uploadFileName}
                                </span>
                                <div class="progress-bar-container">
                                    <div class="progress-bar" style="width: {uploadProgress}%"></div>
                                </div>
                                <span class="upload-progress-percent">{uploadProgress}%</span>
                            {/if}
                        </div>
                    </div>
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
        align-items: center;
        justify-content: center;
        gap: 12px;
        width: 100%;
        text-align: center;
        cursor: pointer;
        padding: 12px 16px;
    }

    .upload-label-text {
        padding-left: 0;
        display: flex;
        align-items: center;
        line-height: 1;
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
        justify-content: center;
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
        justify-content: center;
        gap: 16px;
        padding: 0;
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

    .header-actions {
        font-size: 0.75rem;
        color: var(--text-secondary);
        text-align: center;
        font-weight: 600;
        text-transform: uppercase;
        display: flex;
        justify-content: center;
        align-items: center;
        width: 48px;
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

        .admin-link {
        text-decoration: none;
        display: block;
        width: 100%;
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
        grid-template-columns: auto auto auto 1fr 150px 100px 48px;
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

    .versions-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        color: var(--text-secondary);
        transition: all 0.2s ease;
    }

    .versions-btn:hover {
        background-color: var(--hover-bg);
        color: #fff;
    }

    .versions-btn .feather {
        width: 18px;
        height: 18px;
        stroke: currentColor;
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

    .versions-overlay {
        position: fixed;
        inset: 0;
        background-color: rgba(0, 0, 0, 0.6);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 200;
        padding: 24px;
    }

    .versions-modal {
        width: 100%;
        max-width: 720px;
        background-color: var(--primary-bg);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
        padding: 24px;
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .versions-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }

    .versions-header h3 {
        font-size: 1.25rem;
        font-weight: 600;
    }

    .versions-subtitle {
        font-size: 0.875rem;
        color: var(--text-secondary);
    }

    .versions-close {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        color: var(--text-secondary);
        transition: all 0.2s ease;
    }

    .versions-close:hover {
        background-color: var(--hover-bg);
        color: #fff;
    }

    .versions-state {
        padding: 16px;
        border-radius: 12px;
        background-color: rgba(255, 255, 255, 0.05);
        color: var(--text-secondary);
        text-align: center;
    }

    .versions-state.versions-error {
        color: #fff;
        background-color: rgba(220, 38, 38, 0.3);
    }

    .versions-list {
        list-style: none;
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-height: 360px;
        overflow-y: auto;
        padding-right: 4px;
    }

    .version-item {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 12px 16px;
        border-radius: 12px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid transparent;
    }

    .version-item.is-current {
        border-color: rgba(157, 115, 255, 0.6);
        background-color: rgba(157, 115, 255, 0.12);
    }

    .version-main {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .version-badge {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
    }

    .version-current {
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        background-color: rgba(157, 115, 255, 0.3);
        color: #fff;
    }

    .version-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        color: var(--text-secondary);
        font-size: 0.875rem;
    }

    .version-actions {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
    }

    .version-action {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: 8px;
        background-color: rgba(255, 255, 255, 0.08);
        color: #fff;
        transition: all 0.2s ease;
    }

    .version-action:hover {
        background-color: rgba(255, 255, 255, 0.18);
    }

    .version-action.danger {
        background-color: rgba(220, 38, 38, 0.4);
    }

    .version-action.danger:hover {
        background-color: rgba(220, 38, 38, 0.6);
    }

    .version-action:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .versions-progress {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 12px 16px;
        border-radius: 12px;
        background-color: rgba(255, 255, 255, 0.05);
    }

    .versions-progress-text {
        font-size: 0.875rem;
        color: #fff;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .versions-progress-percent {
        font-size: 0.75rem;
        color: rgba(255, 255, 255, 0.8);
        font-weight: 600;
        text-align: right;
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
            grid-template-columns: auto auto auto 1fr 150px 80px 40px;
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
            grid-template-columns: auto auto auto 1fr 150px 80px 40px;
            gap: 12px;
            padding: 12px 16px;
            min-width: 800px;
        }

        .file-date,
        .file-size {
            display: block;
        }
    }

    /* Progress bar styles */
    .progress-bar-container {
        width: 100%;
        height: 4px;
        background-color: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
        overflow: hidden;
        margin-top: 4px;
    }

    .progress-bar {
        height: 100%;
        background-color: #fff;
        border-radius: 2px;
        transition: width 0.15s ease-out;
    }

    .download-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 200px;
    }

    .download-button .progress-bar-container {
        width: 100px;
        margin-left: 8px;
        margin-top: 0;
    }

    /* Upload progress bar */
    .upload-progress-bar {
        position: absolute;
        top: 80px;
        left: 50%;
        transform: translateX(-50%);
        background-color: var(--primary-purple);
        border-radius: 12px;
        padding: 16px 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        z-index: 100;
        animation: slide-down 0.3s ease-out forwards;
        min-width: 300px;
        max-width: 500px;
    }

    .upload-progress-content {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .upload-progress-content .feather {
        width: 32px;
        height: 32px;
        stroke: #fff;
        flex-shrink: 0;
    }

    .upload-progress-info {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .upload-progress-text {
        font-size: 0.875rem;
        color: #fff;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 350px;
    }

    .upload-progress-percent {
        font-size: 0.75rem;
        color: rgba(255, 255, 255, 0.8);
        font-weight: 600;
    }

    .upload-progress-bar .progress-bar-container {
        height: 6px;
        background-color: rgba(255, 255, 255, 0.3);
    }

    .upload-progress-bar .progress-bar {
        background: linear-gradient(90deg, #fff, rgba(255, 255, 255, 0.9));
    }

    /* Upload error styles */
    .upload-progress-bar.upload-error {
        background-color: #dc2626;
    }

    .upload-error-text {
        font-size: 0.875rem;
        color: #fff;
        font-weight: 500;
        word-break: break-word;
    }

    @keyframes slide-down {
        from {
            opacity: 0;
            transform: translate(-50%, -20px);
        }
        to {
            opacity: 1;
            transform: translate(-50%, 0);
        }
    }
</style>
