
import {
  XIcon,
  SendHorizontal,
  RefreshCcw,
  Pencil,
  Copy,
  CopyCheck,
  ChevronLeft,
  ChevronRight,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { submitFeedback, type FeedbackContext } from "@/lib/feedback-service";
import { toast } from "sonner";
import { TooltipIconButton } from "../tooltip-icon-button";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { Button } from "@/components/ui/button";

function ContentCopyable({
  content,
  disabled,
}: {
  content: string;
  disabled: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    e.stopPropagation();
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <TooltipIconButton
      onClick={(e) => handleCopy(e)}
      variant="ghost"
      tooltip="Copy content"
      disabled={disabled}
    >
      <AnimatePresence
        mode="wait"
        initial={false}
      >
        {copied ? (
          <motion.div
            key="check"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.15 }}
          >
            <CopyCheck className="text-green-500" />
          </motion.div>
        ) : (
          <motion.div
            key="copy"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.15 }}
          >
            <Copy />
          </motion.div>
        )}
      </AnimatePresence>
    </TooltipIconButton>
  );
}

export function BranchSwitcher({
  branch,
  branchOptions,
  onSelect,
  isLoading,
}: {
  branch: string | undefined;
  branchOptions: string[] | undefined;
  onSelect: (branch: string) => void;
  isLoading: boolean;
}) {
  if (!branchOptions || !branch) return null;
  const index = branchOptions.indexOf(branch);

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="ghost"
        size="icon"
        className="size-6 p-1"
        onClick={() => {
          const prevBranch = branchOptions[index - 1];
          if (!prevBranch) return;
          onSelect(prevBranch);
        }}
        disabled={isLoading}
      >
        <ChevronLeft />
      </Button>
      <span className="text-sm">
        {index + 1} / {branchOptions.length}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 p-1"
        onClick={() => {
          const nextBranch = branchOptions[index + 1];
          if (!nextBranch) return;
          onSelect(nextBranch);
        }}
        disabled={isLoading}
      >
        <ChevronRight />
      </Button>
    </div>
  );
}

export function CommandBar({
  content,
  isHumanMessage,
  isAiMessage,
  isEditing,
  setIsEditing,
  handleSubmitEdit,
  handleRegenerate,
  isLoading,
  feedbackContext,
}: {
  content: string;
  isHumanMessage?: boolean;
  isAiMessage?: boolean;
  isEditing?: boolean;
  setIsEditing?: React.Dispatch<React.SetStateAction<boolean>>;
  handleSubmitEdit?: () => void;
  handleRegenerate?: () => void;
  isLoading: boolean;
  /** 反馈上下文，包含问题和SQL，用于点赞/点踩功能 */
  feedbackContext?: FeedbackContext;
}) {
  // 点赞/点踩状态
  const [feedbackGiven, setFeedbackGiven] = useState<'up' | 'down' | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  // 处理点赞
  const handleThumbsUp = async () => {
    if (!feedbackContext || feedbackLoading || feedbackGiven) return;
    
    setFeedbackLoading(true);
    try {
      const result = await submitFeedback(feedbackContext, 'thumbs_up');
      if (result.status === 'success') {
        setFeedbackGiven('up');
        toast.success('感谢您的反馈！', {
          description: '问答对已保存到智能训练中心',
        });
      } else if (result.status === 'error') {
        toast.error('提交反馈失败', {
          description: result.message,
        });
      }
    } catch (error) {
      toast.error('提交反馈失败', {
        description: '请稍后重试',
      });
    } finally {
      setFeedbackLoading(false);
    }
  };

  // 处理点踩
  const handleThumbsDown = async () => {
    if (!feedbackContext || feedbackLoading || feedbackGiven) return;
    
    setFeedbackLoading(true);
    try {
      const result = await submitFeedback(feedbackContext, 'thumbs_down');
      setFeedbackGiven('down');
      toast.info('感谢您的反馈！', {
        description: '我们会持续改进',
      });
    } catch (error) {
      toast.error('提交反馈失败', {
        description: '请稍后重试',
      });
    } finally {
      setFeedbackLoading(false);
    }
  };

  // 是否显示反馈按钮（只有AI消息且有SQL时才显示）
  const showFeedbackButtons = isAiMessage && feedbackContext?.sql;
  if (isHumanMessage && isAiMessage) {
    throw new Error(
      "Can only set one of isHumanMessage or isAiMessage to true, not both.",
    );
  }

  if (!isHumanMessage && !isAiMessage) {
    throw new Error(
      "One of isHumanMessage or isAiMessage must be set to true.",
    );
  }

  if (
    isHumanMessage &&
    (isEditing === undefined ||
      setIsEditing === undefined ||
      handleSubmitEdit === undefined)
  ) {
    throw new Error(
      "If isHumanMessage is true, all of isEditing, setIsEditing, and handleSubmitEdit must be set.",
    );
  }

  const showEdit =
    isHumanMessage &&
    isEditing !== undefined &&
    !!setIsEditing &&
    !!handleSubmitEdit;

  if (isHumanMessage && isEditing && !!setIsEditing && !!handleSubmitEdit) {
    return (
      <div className="flex items-center gap-2">
        <TooltipIconButton
          disabled={isLoading}
          tooltip="Cancel edit"
          variant="ghost"
          onClick={() => {
            setIsEditing(false);
          }}
        >
          <XIcon />
        </TooltipIconButton>
        <TooltipIconButton
          disabled={isLoading}
          tooltip="Submit"
          variant="secondary"
          onClick={handleSubmitEdit}
        >
          <SendHorizontal />
        </TooltipIconButton>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {/* 点赞/点踩按钮 - 只在AI消息且有SQL时显示 */}
      {showFeedbackButtons && (
        <>
          <TooltipIconButton
            disabled={isLoading || feedbackLoading || feedbackGiven !== null}
            tooltip={feedbackGiven === 'up' ? '已点赞' : '这个回答很有帮助'}
            variant="ghost"
            onClick={handleThumbsUp}
          >
            <ThumbsUp 
              className={feedbackGiven === 'up' ? 'text-green-500 fill-green-500' : ''} 
            />
          </TooltipIconButton>
          <TooltipIconButton
            disabled={isLoading || feedbackLoading || feedbackGiven !== null}
            tooltip={feedbackGiven === 'down' ? '已反馈' : '这个回答需要改进'}
            variant="ghost"
            onClick={handleThumbsDown}
          >
            <ThumbsDown 
              className={feedbackGiven === 'down' ? 'text-orange-500 fill-orange-500' : ''} 
            />
          </TooltipIconButton>
          <div className="h-4 w-px bg-border mx-1" /> {/* 分隔线 */}
        </>
      )}
      <ContentCopyable
        content={content}
        disabled={isLoading}
      />
      {isAiMessage && !!handleRegenerate && (
        <TooltipIconButton
          disabled={isLoading}
          tooltip="重新生成"
          variant="ghost"
          onClick={handleRegenerate}
        >
          <RefreshCcw />
        </TooltipIconButton>
      )}
      {showEdit && (
        <TooltipIconButton
          disabled={isLoading}
          tooltip="编辑"
          variant="ghost"
          onClick={() => {
            setIsEditing?.(true);
          }}
        >
          <Pencil />
        </TooltipIconButton>
      )}
    </div>
  );
}
