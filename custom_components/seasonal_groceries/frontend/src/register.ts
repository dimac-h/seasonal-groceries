/**
 * Home Assistant loads extra modules with a bare `import()` that can finish before
 * its own startup has installed the final custom element registry. Elements defined
 * that early are invisible to the dashboard ("Configuration error" cards), so
 * registration waits until Home Assistant's own root element exists.
 */
const POLL_MS = 50;

function homeAssistantReady(): Promise<void> {
  return new Promise(resolve => {
    const check = (): void => {
      if (customElements.get('home-assistant')) resolve();
      else setTimeout(check, POLL_MS);
    };
    check();
  });
}

type Constructor = CustomElementConstructor;

/** Drop-in replacement for lit's `@customElement` that waits for Home Assistant. */
export const customElement =
  (name: string) =>
  (constructor: Constructor): void => {
    void homeAssistantReady().then(() => {
      if (!customElements.get(name)) customElements.define(name, constructor);
    });
  };
