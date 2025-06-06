declare module 'xlsx' {
  export function read(data: string | ArrayBuffer, opts?: any): any
  export namespace utils {
    export function sheet_to_json<T = any>(worksheet: any, opts?: any): T[]
  }
}