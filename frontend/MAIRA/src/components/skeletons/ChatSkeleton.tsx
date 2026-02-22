
import { Skeleton } from "../ui/Skeleton";

export const ChatSkeleton = () => {
    return (
        <div className="mx-auto max-w-4xl w-full px-6 py-12 flex flex-col gap-8">
            {/* User Message (Right) */}
            <div className="flex justify-end">
                <div className="flex flex-col items-end gap-2 max-w-[80%]">
                    <Skeleton className="h-12 w-64 rounded-2xl rounded-tr-sm bg-neutral-800" />
                </div>
            </div>

            {/* AI Message (Left) */}
            <div className="flex justify-start">
                <div className="flex flex-col items-start gap-4 max-w-[80%] w-full">
                    {/* Reason/Thought block */}
                    <Skeleton className="h-8 w-32 rounded-lg bg-neutral-900" />

                    {/* Content */}
                    <div className="space-y-2 w-full">
                        <Skeleton className="h-4 w-full bg-neutral-800" />
                        <Skeleton className="h-4 w-[90%] bg-neutral-800" />
                        <Skeleton className="h-4 w-[95%] bg-neutral-800" />
                    </div>
                </div>
            </div>

            {/* User Message (Right) */}
            <div className="flex justify-end">
                <div className="flex flex-col items-end gap-2 max-w-[80%]">
                    <Skeleton className="h-20 w-80 rounded-2xl rounded-tr-sm bg-neutral-800" />
                </div>
            </div>

            {/* AI Message (Left) */}
            <div className="flex justify-start">
                <div className="flex flex-col items-start gap-4 max-w-[80%] w-full">
                    {/* Content only */}
                    <div className="space-y-2 w-full">
                        <Skeleton className="h-4 w-full bg-neutral-800" />
                        <Skeleton className="h-4 w-[85%] bg-neutral-800" />
                        <Skeleton className="h-4 w-[92%] bg-neutral-800" />
                        <Skeleton className="h-4 w-[60%] bg-neutral-800" />
                    </div>
                </div>
            </div>
        </div>
    );
};
