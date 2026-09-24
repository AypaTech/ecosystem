import { patch } from '@web/core/utils/patch';

import { SuggestionService } from '@mail/core/common/suggestion_service';

patch(SuggestionService.prototype, {
    /**
     * Keep the AI agents suggestible in a private conversation.
     *
     * Discuss narrows the `@` list to the members of a group, a direct chat or
     * a group-restricted channel, so that mentioning somebody cannot leak a
     * private conversation to an outsider who would be notified of it. An
     * agent is no such outsider: it is never a recipient and is never
     * notified, and the run it answers with reads the conversation as the
     * person who mentioned it. So it is added back to the members.
     *
     * @override
     * @param {import("models").Thread} [thread]
     * @returns {import("models").Persona[]}
     */
    getPartnerSuggestions(thread) {
        const suggestions = [...super.getPartnerSuggestions(...arguments)];
        const suggested = new Set(suggestions.map((partner) => partner.id));
        const agents = Object.values(this.store.Persona.records).filter(
            (persona) =>
                persona.type === 'partner' &&
                persona.is_ai_agent &&
                !suggested.has(persona.id),
        );
        return agents.length ? [...suggestions, ...agents] : suggestions;
    },
});
