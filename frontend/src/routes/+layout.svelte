<script lang="ts">
	import favicon from '$lib/assets/favicon.ico';
	import webmanifest from '$lib/assets/site.webmanifest';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link
		href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap"
		rel="stylesheet"
	/>
	<link rel="icon" href={favicon} />
	<link rel="manifest" href={webmanifest} />
	<title>SPCloud</title>
</svelte:head>

{@render children?.()}