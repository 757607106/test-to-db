/**
 * Type extensions for @langchain/langgraph-sdk/react
 * 
 * This file extends the useStream hook return type to include methods
 * that exist at runtime but are missing from the TypeScript type definitions
 * in @langchain/langgraph-sdk@0.1.0
 * 
 * Related issue: setBranch method missing from UseStreamReturn type
 * Date: 2026-01-16
 */

import { type Message, type Checkpoint } from "@langchain/langgraph-sdk";

declare module "@langchain/langgraph-sdk/react" {
  /**
   * Extended return type for useStream hook
   * Adds missing methods that exist at runtime
   */
  export interface UseStreamReturn<TState = any, _TBag = any> {
    /**
     * Set the conversation branch
     * Used for navigating between different conversation branches
     */
    setBranch: (branch: string) => void;
    
    /**
     * Get metadata for a specific message
     * Returns branch information and state details
     */
    getMessagesMetadata: (message: Message) => {
      branch?: string;
      branchOptions?: string[];
      firstSeenState?: {
        parent_checkpoint?: Checkpoint | null;
        values?: TState;
      };
    } | undefined;
  }
}
