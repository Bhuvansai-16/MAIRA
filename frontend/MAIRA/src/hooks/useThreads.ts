import { useContext } from 'react';
import { ThreadContext } from '../context/ThreadContextDefinition';

export const useThreads = () => {
    const context = useContext(ThreadContext);
    if (!context) {
        throw new Error('useThreads must be used within a ThreadProvider');
    }
    return context;
};
