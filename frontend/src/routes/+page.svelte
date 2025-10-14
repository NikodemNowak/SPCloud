<script>
	import { onMount } from 'svelte';

	function redirectToLogin() {
		window.location.href = '/login';
	}

	onMount(() => {
		redirectToLogin();
	});
</script>

