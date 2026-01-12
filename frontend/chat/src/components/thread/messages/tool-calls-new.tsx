
"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Terminal,
  CheckCircle,
  AlertCircle,
  Loader,
  Eye,
  X,
} from "lucide-react";
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";

// Helper function to detect and extract images from text (both base64 and URLs)
function extractImagesFromText(text: string): Array<{ data: string; type: string; original: string; isUrl: boolean }> {
  const images: Array<{ data: string; type: string; original: string; isUrl: boolean }> = [];

  // Pattern 1: Standard data URL format
  const dataUrlPattern = /data:image\/(png|jpeg|jpg|gif|webp|bmp);base64,([A-Za-z0-9+/=]+)/gi;
  let match;
  while ((match = dataUrlPattern.exec(text)) !== null) {
    images.push({
      data: match[0],
      type: match[1],
      original: match[0],
      isUrl: false
    });
  }

  // Pattern 2: HTTP/HTTPS image URLs
  const imageUrlPattern = /https?:\/\/[^\s<>"']+\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s<>"']*)?(?:#[^\s<>"']*)?/gi;
  while ((match = imageUrlPattern.exec(text)) !== null) {
    const url = match[0];
    const extension = url.match(/\.([^.?#]+)(?:\?|#|$)/)?.[1]?.toLowerCase() || 'unknown';
    images.push({
      data: url,
      type: extension,
      original: url,
      isUrl: true
    });
  }

  // Pattern 3: URLs that might be images (common image hosting patterns)
  const possibleImageUrlPatterns = [
    // Alipay CDN pattern (like the example provided)
    /https?:\/\/[^\s<>"']*\.alipayobjects\.com\/[^\s<>"']+/gi,
    // Common image hosting patterns
    /https?:\/\/[^\s<>"']*(?:imgur|cloudinary|amazonaws|googleusercontent|github|githubusercontent)\.com\/[^\s<>"']+/gi,
    // Generic patterns that often contain images
    /https?:\/\/[^\s<>"']*\/[^\s<>"']*(?:image|img|photo|picture|screenshot|pic)[^\s<>"']*/gi,
  ];

  possibleImageUrlPatterns.forEach(pattern => {
    let urlMatch;
    while ((urlMatch = pattern.exec(text)) !== null) {
      const url = urlMatch[0];
      // Avoid duplicates
      if (!images.some(img => img.data === url)) {
        images.push({
          data: url,
          type: 'unknown',
          original: url,
          isUrl: true
        });
      }
    }
  });

  // Pattern 4: JSON field with base64 data (common patterns)
  const jsonPatterns = [
    /"base64Data":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"base64":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"image":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"screenshot":\s*"([A-Za-z0-9+/=]{100,})"/gi,
    /"imageData":\s*"([A-Za-z0-9+/=]{100,})"/gi
  ];

  jsonPatterns.forEach(pattern => {
    let jsonMatch;
    while ((jsonMatch = pattern.exec(text)) !== null) {
      const base64Data = jsonMatch[1];
      // Validate base64 format and reasonable length
      if (base64Data.length > 100 && base64Data.length % 4 === 0) {
        images.push({
          data: `data:image/png;base64,${base64Data}`,
          type: 'png',
          original: jsonMatch[0],
          isUrl: false
        });
      }
    }
  });

  // Pattern 5: Look for very long base64 strings that might be images
  const longBase64Pattern = /([A-Za-z0-9+/=]{1000,})/g;
  while ((match = longBase64Pattern.exec(text)) !== null) {
    const base64Data = match[1];
    // Additional validation: check if it starts with common image signatures
    if (base64Data.length % 4 === 0 &&
        (base64Data.startsWith('iVBORw0KGgo') || // PNG
         base64Data.startsWith('/9j/') || // JPEG
         base64Data.startsWith('R0lGOD') || // GIF
         base64Data.startsWith('UklGR'))) { // WebP
      images.push({
        data: `data:image/png;base64,${base64Data}`,
        type: 'png',
        original: match[0],
        isUrl: false
      });
    }
  }

  // Remove duplicates based on data content
  const uniqueImages = images.filter((img, index, self) =>
    index === self.findIndex(i => i.data === img.data)
  );

  return uniqueImages;
}

// Image Preview Modal Component
function ImagePreviewModal({
  src,
  isOpen,
  onClose
}: {
  src: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div className="relative max-w-[90vw] max-h-[90vh]">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white hover:text-gray-300 z-10"
        >
          <X size={24} />
        </button>
        <img
          src={src}
          alt="Preview"
          className="max-w-full max-h-full object-contain"
          onClick={(e) => e.stopPropagation()}
        />
      </div>
    </div>
  );
}

// Image Display Component
function ImagePreview({ images }: { images: Array<{ data: string; type: string; original: string; isUrl: boolean }> }) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [loadedImages, setLoadedImages] = useState<Set<number>>(new Set());
  const [failedImages, setFailedImages] = useState<Set<number>>(new Set());

  if (images.length === 0) return null;

  const handleImageLoad = (index: number) => {
    setLoadedImages(prev => new Set(prev).add(index));
  };

  const handleImageError = (index: number) => {
    setFailedImages(prev => new Set(prev).add(index));
  };

  const validImages = images.filter((_, index) => !failedImages.has(index));

  if (validImages.length === 0) return null;

  return (
    <>
      <div className="mt-3 space-y-3">
        {images.map((image, index) => {
          if (failedImages.has(index)) return null;

          return (
            <div
              key={index}
              className="relative group cursor-pointer border border-gray-200 rounded-lg overflow-hidden hover:border-gray-300 hover:shadow-md transition-all bg-white"
              onClick={() => setSelectedImage(image.data)}
            >
              {!loadedImages.has(index) && (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
                  <div className="w-6 h-6 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin"></div>
                </div>
              )}
              <img
                src={image.data}
                alt={image.isUrl ? `Image from URL ${index + 1}` : `Generated image ${index + 1}`}
                className="w-full h-auto max-w-full object-contain"
                onLoad={() => handleImageLoad(index)}
                onError={() => handleImageError(index)}
                style={{ display: loadedImages.has(index) ? 'block' : 'none' }}
                crossOrigin={image.isUrl ? "anonymous" : undefined}
              />
              {loadedImages.has(index) && (
                <div className="absolute top-2 right-2 bg-black bg-opacity-50 rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Eye className="text-white" size={16} />
                </div>
              )}
              {/* Show URL indicator for URL-based images */}
              {image.isUrl && loadedImages.has(index) && (
                <div className="absolute bottom-2 left-2 bg-blue-500 bg-opacity-75 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                  URL Image
                </div>
              )}
            </div>
          );
        })}
      </div>

      <ImagePreviewModal
        src={selectedImage || ""}
        isOpen={!!selectedImage}
        onClose={() => setSelectedImage(null)}
      />
    </>
  );
}

// Tool Call interface matching example project
interface ToolCallData {
  id: string;
  name: string;
  args: any;
  result?: string;
  status: "pending" | "completed" | "error";
}

interface ToolCallBoxProps {
  toolCall: NonNullable<AIMessage["tool_calls"]>[0];
  toolResult?: ToolMessage;
}

export const ToolCallBox = React.memo<ToolCallBoxProps>(({ toolCall, toolResult }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const { name, args, result, status, resultText, images } = useMemo(() => {
    const toolName = toolCall?.name?.trim() || "Unknown Tool";
    const toolArgs = toolCall?.args || {};

    let toolResult_content = null;
    let resultAsText = "";

    if (toolResult) {
      try {
        if (typeof toolResult.content === "string") {
          toolResult_content = JSON.parse(toolResult.content);
          resultAsText = toolResult.content;
        } else {
          toolResult_content = toolResult.content;
          resultAsText = JSON.stringify(toolResult.content, null, 2);
        }
      } catch {
        toolResult_content = toolResult.content;
        resultAsText = String(toolResult.content);
      }
    }

    // Extract images from the result text
    const extractedImages = resultAsText ? extractImagesFromText(resultAsText) : [];

    const toolStatus = "completed"; // Default status

    return {
      name: toolName,
      args: toolArgs,
      result: toolResult_content,
      status: toolStatus,
      resultText: resultAsText,
      images: extractedImages,
    };
  }, [toolCall, toolResult]);

  const statusIcon = useMemo(() => {
    const iconProps = { className: "w-3.5 h-3.5" };
    
    switch (status) {
      case "completed":
        return <CheckCircle {...iconProps} className="w-3.5 h-3.5 text-green-500" />;
      case "error":
        return <AlertCircle {...iconProps} className="w-3.5 h-3.5 text-red-500" />;
      case "pending":
        return <Loader {...iconProps} className="w-3.5 h-3.5 text-blue-500 animate-spin" />;
      default:
        return <Terminal {...iconProps} className="w-3.5 h-3.5 text-gray-400" />;
    }
  }, [status]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const hasContent = result || Object.keys(args).length > 0 || images.length > 0;

  return (
    <div className="w-full mb-2">
      {/* Tool Call Box */}
      <div className="border border-gray-200 rounded-md overflow-hidden bg-white">
        <button
          onClick={toggleExpanded}
          className="w-full p-3 flex items-center gap-2 text-left transition-colors hover:bg-gray-50 cursor-pointer disabled:cursor-default"
          disabled={!hasContent}
        >
          {hasContent && isExpanded ? (
            <ChevronDown size={14} className="flex-shrink-0 text-gray-600" />
          ) : (
            <ChevronRight size={14} className="flex-shrink-0 text-gray-600" />
          )}
          {statusIcon}
          <span className="text-sm font-medium text-gray-900">{name}</span>
        </button>

        {isExpanded && hasContent && (
          <div className="px-4 pb-4 bg-gray-50">
            {Object.keys(args).length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  ARGUMENTS
                </h4>
                <pre className="p-3 bg-white border border-gray-200 rounded text-xs font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            )}
            {result && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  RESULT
                </h4>
                <pre className="p-3 bg-white border border-gray-200 rounded text-xs font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0">
                  {typeof result === "string"
                    ? result
                    : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Images displayed outside and below the tool box */}
      <ImagePreview images={images} />
    </div>
  );
});

ToolCallBox.displayName = "ToolCallBox";

export function ToolCalls({
  toolCalls,
  toolResults,
}: {
  toolCalls: AIMessage["tool_calls"];
  toolResults?: ToolMessage[];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  // Filter out invalid tool calls
  const validToolCalls = toolCalls.filter(tc => tc && tc.name && tc.name.trim() !== "");

  return (
    <div className="w-full">
      {validToolCalls.map((tc, idx) => {
        // Find corresponding tool result by tool_call_id
        const correspondingResult = toolResults?.find(
          (result) => result.tool_call_id === tc.id
        );

        return (
          <ToolCallBox
            key={tc.id || idx}
            toolCall={tc}
            toolResult={correspondingResult}
          />
        );
      })}
    </div>
  );
}

// Keep the old ToolResult component for backward compatibility
export function ToolResult({ message }: { message: ToolMessage }) {
  return null; // Hide individual tool results since they're now combined
}
