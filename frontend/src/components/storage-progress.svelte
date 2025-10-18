<script lang="ts">
    let {usedStorage = 0, maxStorage = 100} = $props();

    const progress = $derived(Math.min(usedStorage / maxStorage, 1));
    const percentage = $derived(Math.round(progress * 100));

    const startAngle = 0;
    const totalDegrees = 360;
    const fillDegrees = $derived(totalDegrees * progress);

    const background = $derived(`
		conic-gradient(
			from ${startAngle}deg,
			var(--primary-purple) 0deg,
			var(--primary-purple) ${fillDegrees}deg,
			rgba(140, 98, 255, 0.15) ${fillDegrees}deg,
			rgba(140, 98, 255, 0.15) ${totalDegrees}deg,
			transparent ${totalDegrees}deg
		)
	`);

    const cssVarStyles = $derived(`--background: ${background}`);

    function formatSize(size: number): string {
        return size.toFixed(1);
    }
</script>

<div class="progress-container">
    <div class="progress-circle" style="{cssVarStyles}">
        <div class="progress-inner">
            <div class="progress-text">
                <span class="percentage">{percentage}%</span>
                <span class="storage-info">{formatSize(usedStorage)} / {formatSize(maxStorage)} MB</span>
            </div>
        </div>
    </div>
</div>

<style>
    .progress-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-bottom: 24px;
    }

    .progress-circle {
        background: var(--background);
        border-radius: 50%;
        width: 140px;
        height: 140px;
        transition: all 500ms ease-in;
        display: flex;
        justify-content: center;
        align-items: center;
        position: relative;
    }

    .progress-inner {
        background: var(--sidebar-bg);
        border-radius: 50%;
        width: 100px;
        height: 100px;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
        pointer-events: none;
    }

    .progress-text {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
    }

    .percentage {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
    }

    .storage-info {
        font-size: 0.65rem;
        color: var(--text-primary);
        text-align: center;
        line-height: 1.2;
    }

    @media (max-width: 1200px) {
        .progress-container {
            display: none;
        }
    }

</style>
