import { Component, proxy, t, useProps } from '@odoo/owl';

import { useLayoutEffect } from '@web/owl2/utils';

/**
 * Full-screen blocking overlay that shows a live estimate of the time left
 * until a long-running operation completes.
 */
export class BlockUIProgress extends Component {
    static template = 'BlockUIProgress';
    props = useProps({
        progressData: t.object(),
        totalSteps: t.number(),
    });
    setup() {
        this.timeStart = Date.now();
        this.state = proxy({
            timeLeft: null,
        });
        useLayoutEffect(
            () => {
                this.updateTimer();
                const timer = setInterval(() => this.updateTimer(), 1000);
                return () => {
                    clearInterval(timer);
                };
            },
            () => [],
        );
    }
    get minutesLeft() {
        return this.state.timeLeft.toFixed(2);
    }
    get secondsLeft() {
        return Math.round(this.state.timeLeft * 60);
    }
    /**
     * Recompute the estimated minutes left from the elapsed time and the
     * current progress ratio.
     */
    updateTimer() {
        const elapsedTime = Date.now() - this.timeStart;
        const progress = this.props.progressData.value || 1;
        const remainingRatio = (100 - progress) / progress;
        this.state.timeLeft = (elapsedTime * remainingRatio) / 60000;
    }
}
