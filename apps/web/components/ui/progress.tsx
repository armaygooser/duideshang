"use client";
import * as ProgressPrimitive from "@radix-ui/react-progress";
export function Progress({ value=0 }: { value?: number }) { return <ProgressPrimitive.Root className="progress-root" value={value}><ProgressPrimitive.Indicator className="progress-bar" style={{ transform: `translateX(-${100-value}%)` }} /></ProgressPrimitive.Root>; }
