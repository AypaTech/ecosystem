import { registry } from '@web/core/registry';

import { BlockUIProgress } from '@aypatech_ai_assistant/webutils/core/block_progress/block_progress_ui';

const mainComponentRegistry = registry.category('main_components');

/**
 * Service exposing ``block``/``unblock`` to mount or remove the progress
 * overlay from the main components registry.
 */
export const blockProgressService = {
    start() {
        /**
         * Mount the progress overlay with the given step data.
         * @param {object} data progress payload with ``totalSteps`` and ``progressData``
         */
        function block(data) {
            mainComponentRegistry.add(
                'BlockUIProgress',
                {
                    Component: BlockUIProgress,
                    props: {
                        totalSteps: data.totalSteps,
                        progressData: data.progressData,
                    },
                },
                { force: true },
            );
        }
        function unblock() {
            mainComponentRegistry.remove('BlockUIProgress');
        }
        return {
            block,
            unblock,
        };
    },
};

registry.category('services').add('block_progress', blockProgressService);
