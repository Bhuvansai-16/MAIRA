import { CheckCircle, AlertTriangle, XCircle, Shield, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

export type VerificationStatus = 'VALID' | 'NEEDS_REVISION' | 'INVALID' | 'PENDING' | 'VERIFYING';

interface VerificationBadgeProps {
    status: VerificationStatus;
    score?: number;
    className?: string;
    showLabel?: boolean;
}

export const VerificationBadge = ({ 
    status, 
    score, 
    className,
    showLabel = true 
}: VerificationBadgeProps) => {
    const getStatusConfig = () => {
        switch (status) {
            case 'VALID':
                return {
                    icon: CheckCircle,
                    label: 'Verified',
                    bgColor: 'bg-emerald-500/10',
                    borderColor: 'border-emerald-500/30',
                    textColor: 'text-emerald-400',
                    glowColor: 'shadow-emerald-500/20'
                };
            case 'NEEDS_REVISION':
                return {
                    icon: AlertTriangle,
                    label: 'Needs Review',
                    bgColor: 'bg-amber-500/10',
                    borderColor: 'border-amber-500/30',
                    textColor: 'text-amber-400',
                    glowColor: 'shadow-amber-500/20'
                };
            case 'INVALID':
                return {
                    icon: XCircle,
                    label: 'Issues Found',
                    bgColor: 'bg-red-500/10',
                    borderColor: 'border-red-500/30',
                    textColor: 'text-red-400',
                    glowColor: 'shadow-red-500/20'
                };
            case 'VERIFYING':
                return {
                    icon: Loader2,
                    label: 'Verifying...',
                    bgColor: 'bg-blue-500/10',
                    borderColor: 'border-blue-500/30',
                    textColor: 'text-blue-400',
                    glowColor: 'shadow-blue-500/20'
                };
            default:
                return {
                    icon: Shield,
                    label: 'Pending',
                    bgColor: 'bg-neutral-500/10',
                    borderColor: 'border-neutral-500/30',
                    textColor: 'text-neutral-400',
                    glowColor: 'shadow-neutral-500/20'
                };
        }
    };

    const config = getStatusConfig();
    const Icon = config.icon;

    return (
        <div 
            className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all duration-300",
                config.bgColor,
                config.borderColor,
                `hover:shadow-lg hover:${config.glowColor}`,
                className
            )}
        >
            <Icon 
                size={14} 
                className={cn(
                    config.textColor,
                    status === 'VERIFYING' && 'animate-spin'
                )} 
            />
            {showLabel && (
                <span className={cn(
                    "text-[10px] font-bold uppercase tracking-wider",
                    config.textColor
                )}>
                    {config.label}
                </span>
            )}
            {score !== undefined && (
                <span className={cn(
                    "text-[10px] font-black tabular-nums",
                    config.textColor
                )}>
                    {score}%
                </span>
            )}
        </div>
    );
};

export default VerificationBadge;
