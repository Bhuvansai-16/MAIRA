
import { Skeleton } from "../ui/Skeleton";

export const HomeSkeleton = () => {
    return (
        <div className="min-h-screen bg-black text-white overflow-hidden relative">
            {/* Background Simulation */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-neutral-900 blur-[100px] opacity-20 rounded-full" />
            </div>

            {/* Navbar Skeleton */}
            <div className="fixed top-0 left-0 right-0 z-50 py-6 px-6 border-b border-white/5 bg-black/50 backdrop-blur-md">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-8 w-8 rounded-lg" />
                        <Skeleton className="h-6 w-24" />
                    </div>
                    <div className="hidden md:flex gap-8">
                        <Skeleton className="h-4 w-20" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-16" />
                    </div>
                    <div className="hidden md:flex gap-4">
                        <Skeleton className="h-9 w-20 rounded-full" />
                        <Skeleton className="h-9 w-32 rounded-full" />
                    </div>
                </div>
            </div>

            {/* Hero Skeleton */}
            <section className="relative pt-48 pb-32 px-6">
                <div className="max-w-4xl mx-auto text-center flex flex-col items-center">
                    {/* Badge */}
                    <Skeleton className="h-8 w-64 rounded-full mb-8" />

                    {/* Heading */}
                    <div className="w-full flex flex-col items-center gap-4 mb-8">
                        <Skeleton className="h-16 w-3/4" />
                        <Skeleton className="h-16 w-1/2" />
                    </div>

                    {/* Subtext */}
                    <div className="w-full flex flex-col items-center gap-3 mb-12">
                        <Skeleton className="h-5 w-2/3" />
                        <Skeleton className="h-5 w-1/2" />
                    </div>

                    {/* CTA */}
                    <div className="flex gap-4 mb-20">
                        <Skeleton className="h-14 w-48 rounded-full" />
                    </div>

                    {/* Abstract UI Mockup */}
                    <div className="w-full h-[400px] rounded-xl border border-white/10 bg-neutral-900/40 relative overflow-hidden">
                        <div className="absolute inset-0 p-6 flex flex-col gap-4">
                            <div className="flex gap-2 mb-4">
                                <Skeleton className="h-3 w-3 rounded-full bg-neutral-700" />
                                <Skeleton className="h-3 w-3 rounded-full bg-neutral-700" />
                                <Skeleton className="h-3 w-3 rounded-full bg-neutral-700" />
                            </div>
                            <div className="flex gap-6 h-full">
                                <div className="w-1/4 h-full flex flex-col gap-3">
                                    <Skeleton className="h-4 w-full bg-neutral-800" />
                                    <Skeleton className="h-4 w-3/4 bg-neutral-800" />
                                    <Skeleton className="h-4 w-5/6 bg-neutral-800" />
                                </div>
                                <div className="w-3/4 h-full flex flex-col gap-4">
                                    <Skeleton className="h-8 w-1/2 bg-neutral-800" />
                                    <Skeleton className="h-32 w-full bg-neutral-800 rounded-lg" />
                                    <Skeleton className="h-20 w-3/4 bg-neutral-800 rounded-lg absolute bottom-6 right-6" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Feature Grid Skeleton */}
            <section className="max-w-7xl mx-auto px-6 py-24">
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    {[...Array(6)].map((_, i) => (
                        <Skeleton
                            key={i}
                            className={`h-64 rounded-3xl bg-neutral-900/50 border border-white/5
                        ${i === 0 || i === 3 ? "md:col-span-2" : "col-span-1"}
                    `}
                        />
                    ))}
                </div>
            </section>
        </div>
    );
};
