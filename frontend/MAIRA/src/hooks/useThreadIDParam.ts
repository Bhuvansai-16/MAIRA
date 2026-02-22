import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useCallback, useEffect } from 'react';

export interface UseThreadIDParamOptions {
    paramName?: string; // Default 'threadId'
    syncWithLocalStorage?: boolean; // Keep localStorage in sync
}

export interface UseThreadIDParamReturn {
    threadId: string | undefined;
    setThreadId: (id: string | null) => void;
    hasThreadId: boolean;
    clearThreadId: () => void;
}

export const useThreadIDParam = (options: UseThreadIDParamOptions = {}): UseThreadIDParamReturn => {
    const { paramName = 'threadId', syncWithLocalStorage = true } = options;
    const params = useParams();
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();

    // Get threadId from URL path param (e.g. /chat/:threadId)
    // We prioritize path params over query params if both exist logic-wise, 
    // but React Router usually separates them.
    const threadId = params[paramName];

    // Also optional support for query param ?threadId=...
    // const queryThreadId = searchParams.get(paramName);

    const setThreadId = useCallback((id: string | null) => {
        if (!id) {
            // Remove from URL (navigate to root chat)
            navigate('/chat', { replace: true });
            if (syncWithLocalStorage) {
                localStorage.removeItem('maira_current_thread_id');
            }
        } else {
            // Update URL
            navigate(`/chat/${id}`, { replace: true });
            if (syncWithLocalStorage) {
                localStorage.setItem('maira_current_thread_id', id);
            }
        }
    }, [navigate, syncWithLocalStorage]);

    const clearThreadId = useCallback(() => {
        setThreadId(null);
    }, [setThreadId]);

    return {
        threadId,
        setThreadId,
        hasThreadId: !!threadId,
        clearThreadId
    };
};
