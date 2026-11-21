/* Native bridge. In the browser this file does nothing, so the app keeps its simulated ad and purchase.
   Inside the Capacitor shell it wires the real SDKs behind two small objects the app already knows:
     window.LeonidaAds   -> init(cfg), showRewarded(placement, cfg) => Promise<{rewarded}>
     window.LeonidaStore -> init(cfg), offerings(), buy(plan), restore(), isPro()
   Plugin calls follow @capacitor-community/admob 8 and @revenuecat/purchases-capacitor 14;
   re-check them against the installed versions when the native projects are first built. */
(function () {
  var C = window.Capacitor;
  if (!C || !C.isNativePlatform || !C.isNativePlatform()) return;
  var P = C.Plugins || {}, platform = C.getPlatform(); // 'ios' | 'android'

  /* ---------- ads (AdMob, rewarded) ---------- */
  var AdMob = P.AdMob, adsReady = false, adsInit = null;
  window.LeonidaAds = {
    // Runs once, the first time an ad is asked for: the consent form and the iOS tracking prompt then
    // show up in context (the person just chose to watch an ad) instead of on top of the first screen.
    init: function (cfg) { return adsInit || (adsInit = this._init(cfg)); },
    _init: async function (cfg) {
      if (!AdMob) return;
      try {
        // Consent first: Europe (GDPR/UMP form), then the iOS tracking prompt.
        var info = await AdMob.requestConsentInfo();
        if (info && info.isConsentFormAvailable && info.status === 'REQUIRED') await AdMob.showConsentForm();
        if (platform === 'ios') { try { await AdMob.requestTrackingAuthorization(); } catch (e) {} }
        await AdMob.initialize({ initializeForTesting: !!cfg.testMode });
        adsReady = true;
      } catch (e) { console.warn('ads init', e); }
    },
    showRewarded: async function (placement, cfg) {
      await this.init(cfg);
      if (!AdMob || !adsReady) { adsInit = null; throw new Error('ads not ready'); }
      var ids = cfg[platform] || {}, adId = ids.rewarded;
      if (!adId) throw new Error('missing rewarded ad unit id for ' + platform);
      var rewarded = false;
      var h = await AdMob.addListener('onRewardedVideoAdReward', function () { rewarded = true; });
      try {
        await AdMob.prepareRewardVideoAd({ adId: adId, isTesting: !!cfg.testMode });
        await AdMob.showRewardVideoAd();
      } finally { if (h && h.remove) h.remove(); }
      return { rewarded: rewarded };
    }
  };

  /* ---------- subscriptions (RevenueCat) ---------- */
  var RC = P.Purchases, ENT = 'pro', pro = false, listeners = [];
  function setPro(info) {
    var a = info && info.entitlements && info.entitlements.active;
    var v = !!(a && a[ENT]);
    if (v !== pro) { pro = v; listeners.forEach(function (f) { try { f(pro); } catch (e) {} }); }
    return pro;
  }
  window.LeonidaStore = {
    onChange: function (f) { listeners.push(f); },
    isPro: function () { return pro; },
    init: async function (cfg) {
      if (!RC) return false;
      var key = (cfg.revenuecat || {})[platform];
      if (!key) return false;
      await RC.configure({ apiKey: key });
      var r = await RC.getCustomerInfo();
      return setPro(r.customerInfo);
    },
    // -> { weekly: {price, id}, yearly: {price, id, trialDays} } with prices already localised by the store
    offerings: async function () {
      var o = await RC.getOfferings(), cur = o && o.current, out = {};
      if (!cur) return out;
      (cur.availablePackages || []).forEach(function (p) {
        var kind = p.packageType === 'ANNUAL' ? 'yearly' : p.packageType === 'WEEKLY' ? 'weekly' : null;
        if (kind) out[kind] = { pkg: p, id: p.product.identifier, price: p.product.priceString, amount: p.product.price, currency: p.product.currencyCode };
      });
      return out;
    },
    buy: async function (pkg) {
      var r = await RC.purchasePackage({ aPackage: pkg });
      return setPro(r.customerInfo);
    },
    restore: async function () {
      var r = await RC.restorePurchases();
      return setPro(r.customerInfo);
    }
  };

  /* ---------- launch-day reminder (local notification, nothing leaves the device) ---------- */
  var LN = P.LocalNotifications, NID = 619;
  window.LeonidaNotify = {
    schedule: async function (o) {
      if (!LN) return false;
      var perm = await LN.requestPermissions();
      if (!perm || perm.display !== 'granted') return false;
      try { await LN.cancel({ notifications: [{ id: NID }] }); } catch (e) {}
      await LN.schedule({ notifications: [{ id: NID, title: o.title, body: o.body, schedule: { at: new Date(o.at), allowWhileIdle: true } }] });
      return true;
    },
    cancel: function () { return LN ? LN.cancel({ notifications: [{ id: NID }] }) : Promise.resolve(); }
  };

  /* ---------- forced update (@capawesome/capacitor-app-update 8) ----------
     Android: Google Play says whether a newer build is available to this device. iOS: App Store lookup by bundle id
     for the person's country. open() goes to the store entry; Play and the App Store pick the person's own
     language and country. iOS needs the numeric Apple id (UPD_CFG.appleId) once the app exists on the App Store. */
  var AU = P.AppUpdate;
  function verCmp(a, b) { // "1.10.0" vs "1.9.2"
    var x = String(a).split('.'), y = String(b).split('.');
    for (var i = 0; i < Math.max(x.length, y.length); i++) { var d = (parseInt(x[i], 10) || 0) - (parseInt(y[i], 10) || 0); if (d) return d > 0 ? 1 : -1; }
    return 0;
  }
  window.LeonidaUpdate = {
    check: async function (country) {
      if (!AU) return { available: false };
      try {
        var i = await AU.getAppUpdateInfo(platform === 'ios' ? { country: country } : undefined), av = false;
        if (platform === 'android') av = i.updateAvailability === 2;
        else av = !!(i.availableVersionName && verCmp(i.availableVersionName, i.currentVersionName) > 0);
        return { available: av, info: i };
      } catch (e) { return { available: false }; }
    },
    open: async function (country, cfg) {
      if (!AU) return;
      if (platform === 'ios') { if (cfg && cfg.appleId) return AU.openAppStore({ appId: cfg.appleId }); return; }
      return AU.openAppStore();
    }
  };

  /* ---------- small native niceties ---------- */
  if (P.StatusBar) { try { P.StatusBar.setStyle({ style: 'DARK' }); } catch (e) {} }
  if (P.App) P.App.addListener('backButton', function () {
    if (document.querySelector('#upd:not([hidden])')) return; // forced update: no way around it
    var back = document.querySelector('#hdr [data-act=back], #pw:not([hidden]) [data-act=pwclose]');
    if (back) back.click(); else P.App.exitApp();
  });
})();
