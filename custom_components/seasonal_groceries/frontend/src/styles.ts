import { css } from 'lit';

/** Styles shared by the cards. Theme variables and --ha-space-* tokens only. */
export const sharedStyles = css`
  :host {
    display: block;
  }
  ha-card {
    padding: var(--ha-space-4, 16px);
  }
  .header {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    margin-block-end: var(--ha-space-4, 16px);
    font-size: var(--ha-font-size-l, 18px);
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .subtitle {
    color: var(--secondary-text-color);
    font-size: 14px;
    font-weight: 400;
  }
  .row {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    padding-block: var(--ha-space-2, 8px);
    color: var(--primary-text-color);
  }
  .row .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .band {
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    color: var(--secondary-text-color);
    font-size: 12px;
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .empty {
    padding: var(--ha-space-6, 24px);
    text-align: center;
    color: var(--secondary-text-color);
  }
  .muted {
    color: var(--secondary-text-color);
  }
`;
