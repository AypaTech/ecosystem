import { useEffect } from '@odoo/owl';
import { user } from '@web/core/user';
import { url } from '@web/core/utils/urls';
import { useBus, useService } from '@web/core/utils/hooks';

import { Dropdown } from '@web/core/dropdown/dropdown';

/**
 * Apps-menu dropdown that renders a full-screen app grid, optionally over a
 * company background image, and opens the command palette as the user types.
 */
export class AppsMenu extends Dropdown {
    setup() {
        super.setup();
        this.commandPaletteOpen = false;
        this.commandService = useService('command');
        this.imageUrl = user.activeCompany.has_background_image
            ? url('/web/image', {
                  model: 'res.company',
                  field: 'background_image',
                  id: user.activeCompany.id,
              })
            : null;
        useEffect(
            (isOpen) => {
                if (isOpen) {
                    const openMainPalette = (ev) => {
                        if (
                            !this.commandPaletteOpen &&
                            ev.key.length === 1 &&
                            !ev.ctrlKey &&
                            !ev.altKey
                        ) {
                            this.commandService.openMainPalette(
                                { searchValue: `/${ev.key}` },
                                () => {
                                    this.commandPaletteOpen = false;
                                },
                            );
                            this.commandPaletteOpen = true;
                        }
                    };
                    window.addEventListener('keydown', openMainPalette);
                    return () => {
                        window.removeEventListener('keydown', openMainPalette);
                        this.commandPaletteOpen = false;
                    };
                }
            },
            () => [this.state.isOpen],
        );
        useBus(this.env.bus, 'ACTION_MANAGER:UI-UPDATED', () => {
            if (this.state.isOpen) {
                this.state.close();
            }
        });
    }
    onOpened() {
        super.onOpened();
        if (this.imageUrl && this.menuRef && this.menuRef.el) {
            this.menuRef.el.style.backgroundImage = `url('${this.imageUrl}')`;
        }
    }
}
