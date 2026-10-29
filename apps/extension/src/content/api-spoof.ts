// apps/extension/src/content/api-spoof.ts

(function () {
  // 1. Singleton Native Code Masking Registry
  const nativeToString = Function.prototype.toString;
  const spoofedFunctions = new WeakSet<object>();

  Function.prototype.toString = function () {
    if (spoofedFunctions.has(this)) {
      return `function ${this.name || ''}() { [native code] }`;
    }
    return nativeToString.call(this);
  };
  
  // Mask our own toString override
  spoofedFunctions.add(Function.prototype.toString);

  const stealthProxy = <T extends object, K extends keyof T>(
    targetObj: T,
    targetMethod: K,
    proxyHandler: ProxyHandler<(...args: any[]) => any>
  ) => {
    try {
      const original = targetObj[targetMethod];
      if (typeof original !== 'function') return;

      const proxy = new Proxy(original as unknown as (...args: any[]) => any, proxyHandler);
      spoofedFunctions.add(proxy as unknown as object);
      targetObj[targetMethod] = proxy as unknown as T[K];
    } catch (e) { /* Ignore strict mode/CSP blocks */ }
  };

  // 0. Listen for CSP-compliant Shield Updates from ISOLATED world
  try {
    document.addEventListener('__ssense_shield_update__', (event: any) => {
      const detail = event?.detail;
      if (!detail) return;
      if (Array.isArray(detail.badDomains)) {
        (window as any).__ssenseBlockedDomains = detail.badDomains;
      }
      if (typeof detail.stripTelemetry === 'boolean') {
        (window as any).__ssenseStripTelemetry = detail.stripTelemetry;
      }
      if (typeof detail.spoofHardware === 'boolean') {
        (window as any).__ssenseSpoofHardware = detail.spoofHardware;
      }
    });
  } catch (e) {}

  const matchesBlockedDomain = (urlStr: string, badDomains: string[]): boolean => {
    if (!urlStr || !badDomains || !badDomains.length) return false;
    try {
      const parsed = new URL(urlStr, window.location.href);
      const host = parsed.hostname.toLowerCase();
      return badDomains.some((d) => {
        const target = d.toLowerCase().trim();
        return host === target || host.endsWith('.' + target);
      });
    } catch {
      const lower = urlStr.toLowerCase();
      return badDomains.some((d) => lower.includes(d.toLowerCase()));
    }
  };

  const applySpoofs = (targetWindow: any) => {
    try {
      // 2. Enforce Global Privacy Control (GPC)
      if (targetWindow.Navigator && !('globalPrivacyControl' in targetWindow.Navigator.prototype)) {
        const gpcGetter = function globalPrivacyControl() { return true; };
        spoofedFunctions.add(gpcGetter);
        Object.defineProperty(targetWindow.Navigator.prototype, 'globalPrivacyControl', {
          get: gpcGetter, configurable: false, enumerable: true,
        });
      }

      // 🚀 Hardware Fingerprinting Defenses (Activated conditionally on audit requirement)
      if (targetWindow.Navigator && 'hardwareConcurrency' in targetWindow.Navigator.prototype) {
        const originalHw = targetWindow.Navigator.prototype.hardwareConcurrency;
        const hwGetter = function hardwareConcurrency() {
          return (window as any).__ssenseSpoofHardware ? 8 : (originalHw ?? 8);
        };
        spoofedFunctions.add(hwGetter);
        Object.defineProperty(targetWindow.Navigator.prototype, 'hardwareConcurrency', {
          get: hwGetter, configurable: false, enumerable: true,
        });
      }

      if (targetWindow.AudioContext && targetWindow.AudioContext.prototype) {
        const originalLatency = targetWindow.AudioContext.prototype.baseLatency;
        const latencyGetter = function baseLatency() {
          return (window as any).__ssenseSpoofHardware ? 0.005 : (originalLatency ?? 0.005);
        };
        spoofedFunctions.add(latencyGetter);
        Object.defineProperty(targetWindow.AudioContext.prototype, 'baseLatency', {
          get: latencyGetter, configurable: true, enumerable: true,
        });
      }

      if (targetWindow.navigator && 'gpu' in targetWindow.navigator && targetWindow.navigator.gpu) {
        stealthProxy(targetWindow.navigator.gpu, 'requestAdapter', {
          async apply(target, thisArg, args) {
            const adapter = await Reflect.apply(target, thisArg, args);
            if ((window as any).__ssenseSpoofHardware && adapter && 'requestAdapterInfo' in adapter) {
              stealthProxy(adapter, 'requestAdapterInfo', {
                async apply() {
                  return { vendor: 'Intel Inc.', architecture: 'Gen12', device: 'Intel Iris OpenGL Engine', description: 'Standard GPU' };
                }
              });
            }
            return adapter;
          }
        });
      }
    } catch (e) {}

    // 3. Spoof WebGL Renderer (Only when hardware masking is engaged)
    if (targetWindow.WebGLRenderingContext) {
      stealthProxy(targetWindow.WebGLRenderingContext.prototype, 'getParameter', {
        apply(target, thisArg, args) {
          if ((window as any).__ssenseSpoofHardware) {
            const parameter = args[0];
            if (parameter === 37445) return 'Intel Inc.'; 
            if (parameter === 37446) return 'Intel Iris OpenGL Engine'; 
          }
          return Reflect.apply(target, thisArg, args);
        },
      });
    }
    
    // 4. Spoof Canvas Fingerprinting (Only when hardware masking is engaged)
    if (targetWindow.HTMLCanvasElement) {
      stealthProxy(targetWindow.HTMLCanvasElement.prototype, 'toDataURL', {
        apply(target, thisArg, args) {
          if (!(window as any).__ssenseSpoofHardware) {
            return Reflect.apply(target, thisArg, args);
          }
          const type = args[0];
          if (type === 'image/png' || type === 'image/jpeg') {
            try {
              const ctx = thisArg.getContext('2d');
              if (ctx) {
                const imageData = ctx.getImageData(0, 0, thisArg.width, thisArg.height);
                imageData.data[0] = imageData.data[0] ^ 1; // Flip LSB of Red channel
                ctx.putImageData(imageData, 0, 0);
              }
            } catch (e) { /* Tainted canvas */ }
          }
          return Reflect.apply(target, thisArg, args);
        },
      });
    }

    if (targetWindow.CanvasRenderingContext2D && targetWindow.CanvasRenderingContext2D.prototype) {
      stealthProxy(targetWindow.CanvasRenderingContext2D.prototype, 'getImageData', {
        apply(target, thisArg, args) {
          const imageData = Reflect.apply(target, thisArg, args);
          if ((window as any).__ssenseSpoofHardware && imageData && imageData.data && imageData.data.length > 0) {
            imageData.data[0] = imageData.data[0] ^ 1; // Flip LSB of Red channel
          }
          return imageData;
        }
      });
    }
  };

  applySpoofs(window);

  // 5. Defeat the "Clean Room" iframe bypass & intercept dynamic tracker script insertions
  if (typeof Node !== 'undefined') {
    const handleNodeInsertion = (node: Node) => {
      if (!node) return;
      const badDomains: string[] = (window as any).__ssenseBlockedDomains || [];
      const nodeName = node.nodeName;

      if ((nodeName === 'SCRIPT' || nodeName === 'IFRAME') && badDomains.length > 0) {
        const src = (node as any).src;
        if (src && matchesBlockedDomain(src, badDomains)) {
          console.warn(`[Ssense Shield] Blocked dynamic ${nodeName} insertion from tracker: ${src}`);
          try { (node as any).src = 'about:blank'; } catch {}
          return false;
        }
      }

      if (nodeName === 'IFRAME') {
        const iframe = node as HTMLIFrameElement;
        if (iframe.contentWindow) {
          try { applySpoofs(iframe.contentWindow); } catch (e) {}
        }
      }
      return true;
    };

    stealthProxy(Node.prototype, 'appendChild', {
      apply(target, thisArg, args) {
        const node = args[0] as Node;
        if (node && handleNodeInsertion(node) === false) {
          return node; // Return node without inserting into DOM
        }
        const result = Reflect.apply(target, thisArg, args);
        if (node && node.nodeName === 'IFRAME') {
          const iframe = node as HTMLIFrameElement;
          if (iframe.contentWindow) {
            try { applySpoofs(iframe.contentWindow); } catch (e) {}
          }
        }
        return result;
      }
    });

    stealthProxy(Node.prototype, 'insertBefore', {
      apply(target, thisArg, args) {
        const node = args[0] as Node;
        if (node && handleNodeInsertion(node) === false) {
          return node;
        }
        const result = Reflect.apply(target, thisArg, args);
        if (node && node.nodeName === 'IFRAME') {
          const iframe = node as HTMLIFrameElement;
          if (iframe.contentWindow) {
            try { applySpoofs(iframe.contentWindow); } catch (e) {}
          }
        }
        return result;
      }
    });
  }

  // 6. Defeat the Getter Bypass
  try {
    if (typeof HTMLIFrameElement !== 'undefined') {
      const originalContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
      if (originalContentWindow && originalContentWindow.get) {
        const contentWindowGetter = function contentWindow(this: HTMLIFrameElement) {
          const cw = originalContentWindow.get!.call(this);
          if (cw) { try { applySpoofs(cw); } catch (e) {} }
          return cw;
        };
        spoofedFunctions.add(contentWindowGetter);
        Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
          get: contentWindowGetter, configurable: true, enumerable: true,
        });
      }
    }
  } catch (e) {}

  // 7. Network Telemetry & Tracker Interception Hooks (fetch / XHR)
  try {
    if (typeof window !== 'undefined' && typeof window.fetch === 'function') {
      stealthProxy(window, 'fetch', {
        apply(target, thisArg, args) {
          const urlStr = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) ? args[0].url : '';
          const badDomains: string[] = (window as any).__ssenseBlockedDomains || [];
          if (urlStr && matchesBlockedDomain(urlStr, badDomains)) {
            console.warn(`[Ssense Shield] Aborted blocked fetch request: ${urlStr}`);
            return Promise.reject(new TypeError('Failed to fetch (Ssense DPDP Shield Blocked)'));
          }
          if ((window as any).__ssenseStripTelemetry && args[1] && args[1].headers) {
            const cleanHeaders = new Headers(args[1].headers);
            ['x-telemetry', 'x-tracker', 'x-analytics', 'x-mixpanel', 'x-client-data'].forEach(h => cleanHeaders.delete(h));
            args[1].headers = cleanHeaders;
          }
          return Reflect.apply(target, thisArg, args);
        }
      });
    }

    if (typeof XMLHttpRequest !== 'undefined' && typeof XMLHttpRequest.prototype.open === 'function') {
      stealthProxy(XMLHttpRequest.prototype, 'open', {
        apply(target, thisArg, args) {
          const urlStr = typeof args[1] === 'string' ? args[1] : '';
          const badDomains: string[] = (window as any).__ssenseBlockedDomains || [];
          if (urlStr && matchesBlockedDomain(urlStr, badDomains)) {
            console.warn(`[Ssense Shield] Aborted blocked XHR request: ${urlStr}`);
            (thisArg as any).__ssenseBlocked = true;
          }
          return Reflect.apply(target, thisArg, args);
        }
      });

      stealthProxy(XMLHttpRequest.prototype, 'setRequestHeader', {
        apply(target, thisArg, args) {
          const headerName = typeof args[0] === 'string' ? args[0].toLowerCase() : '';
          if ((window as any).__ssenseStripTelemetry && ['x-telemetry', 'x-tracker', 'x-analytics', 'x-mixpanel', 'x-client-data'].includes(headerName)) {
            return; // Drop telemetry tracking header silently
          }
          return Reflect.apply(target, thisArg, args);
        }
      });

      stealthProxy(XMLHttpRequest.prototype, 'send', {
        apply(target, thisArg, args) {
          if ((thisArg as any).__ssenseBlocked) {
            thisArg.dispatchEvent(new Event('error'));
            return;
          }
          return Reflect.apply(target, thisArg, args);
        }
      });
    }

    // 8. Intercept navigator.sendBeacon Telemetry
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      stealthProxy(navigator, 'sendBeacon', {
        apply(target, thisArg, args) {
          const urlStr = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) ? args[0].url : '';
          const badDomains: string[] = (window as any).__ssenseBlockedDomains || [];
          if (urlStr && matchesBlockedDomain(urlStr, badDomains)) {
            console.warn(`[Ssense Shield] Aborted blocked sendBeacon telemetry: ${urlStr}`);
            return true; // Pretend queued successfully so site doesn't retry
          }
          return Reflect.apply(target, thisArg, args);
        }
      });
    }
  } catch (e) {}
})();