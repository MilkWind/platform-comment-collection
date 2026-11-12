// Copy SESSDATA from the browser console on https://www.bilibili.com (logged in).
// If SESSDATA is HttpOnly, this prints a warning; fall back to copying a request
// as cURL from DevTools -> Network -> any api.bilibili.com request.
(() => {
  const m = document.cookie.match(/(?:^|;\s*)SESSDATA=([^;]+)/);
  m
    ? copy('SESSDATA=' + m[1])
    : console.warn(
        'SESSDATA is HttpOnly here. Use Network -> any api.bilibili.com request ' +
          '-> Copy as cURL, then paste that into the app.'
      );
})();
