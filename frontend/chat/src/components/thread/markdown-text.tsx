"use client";

import "./markdown-styles.css";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import { FC, memo, useState, useEffect, useRef } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { SyntaxHighlighter } from "@/components/thread/syntax-highlighter";

import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { cn } from "@/lib/utils";

import "katex/dist/katex.min.css";

// 打字机效果 Hook
const useTypewriter = (text: string, speed: number = 5, enabled: boolean = true) => {
  const [displayedText, setDisplayedText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  
  // 引用保持最新的 text，避免 effect 闭包问题
  const textRef = useRef(text);
  const displayedRef = useRef("");
  
  useEffect(() => {
    if (!enabled) {
      return;
    }

    textRef.current = text;
    setIsTyping(true);
    
    // 如果文本缩短了（比如重置），直接重置
    if (text.length < displayedRef.current.length) {
      displayedRef.current = text;
      setDisplayedText(text);
      return;
    }
    
    // 如果已经显示完了，不需要定时器
    if (displayedRef.current.length === text.length) {
      setIsTyping(false);
      return;
    }

    const timer = setInterval(() => {
      const current = displayedRef.current;
      const target = textRef.current;
      
      if (current.length < target.length) {
        // 每次增加的字符数，根据剩余长度动态调整，避免长文本卡顿
        const remaining = target.length - current.length;
        const step = Math.max(1, Math.ceil(remaining / 20)); // 动态步长
        
        const next = target.slice(0, current.length + step);
        displayedRef.current = next;
        setDisplayedText(next);
      } else {
        setIsTyping(false);
        clearInterval(timer);
      }
    }, speed);

    return () => clearInterval(timer);
  }, [text, speed, enabled]);

  if (!enabled) {
    return { displayedText: text, isTyping: false };
  }

  return { displayedText, isTyping };
};

interface CodeHeaderProps {
  language?: string;
  code: string;
}

const useCopyToClipboard = ({
  copiedDuration = 3000,
}: {
  copiedDuration?: number;
} = {}) => {
  const [isCopied, setIsCopied] = useState<boolean>(false);

  const copyToClipboard = async (value: string) => {
    if (!value) return;

    try {
      // 优先使用现代 Clipboard API（需要 HTTPS 或 localhost）
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        await navigator.clipboard.writeText(value);
      } else {
        // 备用方案：使用 execCommand（支持 HTTP 环境）
        const textArea = document.createElement('textarea');
        textArea.value = value;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), copiedDuration);
    } catch (err) {
      console.error('复制失败:', err);
    }
  };

  return { isCopied, copyToClipboard };
};

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();
  const onCopy = () => {
    if (!code || isCopied) return;
    copyToClipboard(code);
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-t-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">
      <span className="lowercase [&>span]:text-xs">{language}</span>
      <TooltipIconButton
        tooltip="Copy"
        onClick={onCopy}
      >
        {!isCopied && <CopyIcon />}
        {isCopied && <CheckIcon />}
      </TooltipIconButton>
    </div>
  );
};

const defaultComponents: any = {
  h1: ({ className, ...props }: { className?: string }) => (
    <h1
      className={cn(
        "mb-8 scroll-m-20 text-4xl font-extrabold tracking-tight last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h2: ({ className, ...props }: { className?: string }) => (
    <h2
      className={cn(
        "mt-8 mb-4 scroll-m-20 text-3xl font-semibold tracking-tight first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h3: ({ className, ...props }: { className?: string }) => (
    <h3
      className={cn(
        "mt-6 mb-4 scroll-m-20 text-2xl font-semibold tracking-tight first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h4: ({ className, ...props }: { className?: string }) => (
    <h4
      className={cn(
        "mt-6 mb-4 scroll-m-20 text-xl font-semibold tracking-tight first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h5: ({ className, ...props }: { className?: string }) => (
    <h5
      className={cn(
        "my-4 text-lg font-semibold first:mt-0 last:mb-0",
        className,
      )}
      {...props}
    />
  ),
  h6: ({ className, ...props }: { className?: string }) => (
    <h6
      className={cn("my-4 font-semibold first:mt-0 last:mb-0", className)}
      {...props}
    />
  ),
  p: ({ className, ...props }: { className?: string }) => (
    <p
      className={cn("mt-5 mb-5 leading-7 first:mt-0 last:mb-0", className)}
      {...props}
    />
  ),
  a: ({ className, href, ...props }: { className?: string; href?: string }) => (
    <a
      className={cn(
        "text-primary font-medium underline underline-offset-4 cursor-pointer hover:text-primary/80 transition-colors",
        className,
      )}
      href={href}
      target={href?.startsWith('http') ? '_blank' : undefined}
      rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }: { className?: string }) => (
    <blockquote
      className={cn("border-l-2 pl-6 italic", className)}
      {...props}
    />
  ),
  ul: ({ className, ...props }: { className?: string }) => (
    <ul
      className={cn("my-5 ml-6 list-disc [&>li]:mt-2", className)}
      {...props}
    />
  ),
  ol: ({ className, ...props }: { className?: string }) => (
    <ol
      className={cn("my-5 ml-6 list-decimal [&>li]:mt-2", className)}
      {...props}
    />
  ),
  hr: ({ className, ...props }: { className?: string }) => (
    <hr
      className={cn("my-5 border-b", className)}
      {...props}
    />
  ),
  table: ({ className, ...props }: { className?: string }) => (
    <table
      className={cn(
        "my-5 w-full border-separate border-spacing-0 overflow-y-auto",
        className,
      )}
      {...props}
    />
  ),
  th: ({ className, ...props }: { className?: string }) => (
    <th
      className={cn(
        "bg-muted px-4 py-2 text-left font-bold first:rounded-tl-lg last:rounded-tr-lg [&[align=center]]:text-center [&[align=right]]:text-right",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }: { className?: string }) => (
    <td
      className={cn(
        "border-b border-l px-4 py-2 text-left last:border-r [&[align=center]]:text-center [&[align=right]]:text-right",
        className,
      )}
      {...props}
    />
  ),
  tr: ({ className, ...props }: { className?: string }) => (
    <tr
      className={cn(
        "m-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-bl-lg [&:last-child>td:last-child]:rounded-br-lg",
        className,
      )}
      {...props}
    />
  ),
  sup: ({ className, ...props }: { className?: string }) => (
    <sup
      className={cn("[&>a]:text-xs [&>a]:no-underline", className)}
      {...props}
    />
  ),
  pre: ({ className, ...props }: { className?: string }) => (
    <pre
      className={cn(
        "max-w-4xl overflow-x-auto rounded-lg bg-black text-white",
        className,
      )}
      {...props}
    />
  ),
  code: ({
    className,
    children,
    ...props
  }: {
    className?: string;
    children: React.ReactNode;
  }) => {
    const match = /language-(\w+)/.exec(className || "");

    if (match) {
      const language = match[1];
      const code = String(children).replace(/\n$/, "");

      return (
        <>
          <CodeHeader
            language={language}
            code={code}
          />
          <SyntaxHighlighter
            language={language}
            className={className}
          >
            {code}
          </SyntaxHighlighter>
        </>
      );
    }

    return (
      <code
        className={cn("rounded font-semibold", className)}
        {...props}
      >
        {children}
      </code>
    );
  },
  img: ({ className, src, alt, ...props }: { className?: string; src?: string; alt?: string }) => (
    <img
      className={cn(
        "max-w-full h-auto rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow cursor-pointer my-4",
        className,
      )}
      src={src}
      alt={alt || "Image"}
      style={{ maxHeight: '400px', objectFit: 'contain' }}
      onClick={() => src && window.open(src, '_blank')}
      {...props}
    />
  ),
};

const MarkdownTextImpl: FC<{ children: string; shouldAnimate?: boolean }> = ({ 
  children,
  shouldAnimate = true
}) => {
  // 如果内容是 JSON，则不使用打字机效果，直接渲染
  // 简单的 JSON 检测：以 { 或 [ 开头，以 } 或 ] 结尾
  const isJson = (children.trim().startsWith('{') && children.trim().endsWith('}')) || 
                 (children.trim().startsWith('[') && children.trim().endsWith(']'));
  
  // 如果是 JSON，或者内容很短（可能是加载中），或者内容很长（历史消息），可以考虑跳过打字机
  // 这里主要解决 JSON 逐字显示的问题
  // 如果外部传入 shouldAnimate=false，则强制跳过
  const shouldSkipTypewriter = !shouldAnimate || isJson;

  const { displayedText, isTyping } = useTypewriter(children, 10, !shouldSkipTypewriter);
  
  const textToRender = displayedText;
  const showCursor = !shouldSkipTypewriter && isTyping;
  
  return (
    <div className="markdown-content relative">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={defaultComponents}
      >
        {textToRender}
      </ReactMarkdown>
      {showCursor && (
         <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1 align-middle" />
      )}
    </div>
  );
};

export const MarkdownText = memo(MarkdownTextImpl);

