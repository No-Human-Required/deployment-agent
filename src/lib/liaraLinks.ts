/** Open a Liara app/service in the public console. */
export function liaraServiceConsoleUrl(serviceName: string): string {
  const name = serviceName.trim();
  return `https://console.liara.ir/apps/${encodeURIComponent(name)}`;
}
