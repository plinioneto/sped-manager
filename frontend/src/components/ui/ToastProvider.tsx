import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react"

type ToastKind = "success" | "error" | "warning" | "info"

interface Toast {
  id: number
  kind: ToastKind
  message: string
  duration: number
  onUndo?: () => void
}

interface DestructiveOptions {
  delay?: number
}

interface ToastContextValue {
  success: (message: string, duration?: number) => void
  error: (message: string, duration?: number) => void
  warning: (message: string, duration?: number) => void
  info: (message: string, duration?: number) => void
  destructive: (message: string, onConfirm: () => void, options?: DestructiveOptions) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

const KIND_STYLES: Record<ToastKind, string> = {
  success: "bg-emerald-50 border-emerald-200 text-emerald-800",
  error: "bg-rose-50 border-rose-200 text-rose-800",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-blue-50 border-blue-200 text-blue-800",
}

const KIND_BAR: Record<ToastKind, string> = {
  success: "bg-emerald-500",
  error: "bg-rose-500",
  warning: "bg-amber-500",
  info: "bg-blue-500",
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({})

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    clearTimeout(timers.current[id])
    delete timers.current[id]
  }, [])

  const push = useCallback(
    (kind: ToastKind, message: string, duration = 4000) => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, kind, message, duration }])
      if (duration > 0) {
        timers.current[id] = setTimeout(() => dismiss(id), duration)
      }
    },
    [dismiss],
  )

  const destructive = useCallback(
    (message: string, onConfirm: () => void, options?: DestructiveOptions) => {
      const delay = options?.delay ?? 5000
      const id = nextId.current++
      const onUndo = () => {
        clearTimeout(timers.current[id])
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }
      setToasts((prev) => [...prev, { id, kind: "warning", message, duration: delay, onUndo }])
      timers.current[id] = setTimeout(() => {
        onConfirm()
        dismiss(id)
      }, delay)
    },
    [dismiss],
  )

  const value: ToastContextValue = {
    success: (m, d) => push("success", m, d),
    error: (m, d) => push("error", m, d),
    warning: (m, d) => push("warning", m, d),
    info: (m, d) => push("info", m, d),
    destructive,
    dismiss,
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  return (
    <div className={`relative overflow-hidden rounded-lg border shadow-sm px-4 py-3 text-sm ${KIND_STYLES[toast.kind]}`}>
      <div className="flex items-start justify-between gap-3">
        <span>{toast.message}</span>
        <div className="flex items-center gap-2 shrink-0">
          {toast.onUndo && (
            <button onClick={toast.onUndo} className="font-medium underline">
              Desfazer
            </button>
          )}
          <button onClick={onDismiss} className="opacity-60 hover:opacity-100">
            ×
          </button>
        </div>
      </div>
      {toast.duration > 0 && (
        <div
          className={`absolute left-0 bottom-0 h-0.5 ${KIND_BAR[toast.kind]} animate-toast-progress`}
          style={{ animationDuration: `${toast.duration}ms` }}
        />
      )}
    </div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error("useToast precisa estar dentro de <ToastProvider>")
  return ctx
}
