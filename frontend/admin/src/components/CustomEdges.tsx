import React from 'react';
import {
  EdgeProps,
  getBezierPath,
  getSmoothStepPath,
  getStraightPath,
  EdgeLabelRenderer,
  BaseEdge,
  MarkerType
} from 'reactflow';
import { motion } from 'framer-motion';

// 动画流动边
export const AnimatedEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <defs>
        <linearGradient id={`gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#1890ff" stopOpacity="0.8" />
          <stop offset="50%" stopColor="#40a9ff" stopOpacity="1" />
          <stop offset="100%" stopColor="#69c0ff" stopOpacity="0.8" />
        </linearGradient>
        <filter id={`glow-${id}`}>
          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
          <feMerge> 
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      {/* 发光背景 */}
      <path
        id={`${id}-glow`}
        style={{
          ...style,
          stroke: `url(#gradient-${id})`,
          strokeWidth: 6,
          fill: 'none',
          opacity: 0.3,
          filter: `url(#glow-${id})`
        }}
        className="react-flow__edge-path"
        d={edgePath}
      />
      
      {/* 主边 */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: `url(#gradient-${id})`,
          strokeWidth: 4,
          strokeDasharray: '8 4',
          animation: 'dash 1.5s linear infinite'
        }}
        markerEnd={markerEnd}
      />
      
      {/* 流动粒子效果 */}
      <motion.circle
        r="3"
        fill="#1890ff"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ 
          pathLength: 1, 
          opacity: [0, 1, 1, 0],
          scale: [0.5, 1, 1, 0.5]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "linear"
        }}
      >
        <animateMotion dur="2s" repeatCount="indefinite">
          <mpath href={`#${id}-glow`} />
        </animateMotion>
      </motion.circle>
    </>
  );
};

// 脉冲边
export const PulseEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) => {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 20,
  });

  return (
    <>
      <defs>
        <linearGradient id={`pulse-gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#f093fb" stopOpacity="0.8" />
          <stop offset="50%" stopColor="#f5576c" stopOpacity="1" />
          <stop offset="100%" stopColor="#4facfe" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: `url(#pulse-gradient-${id})`,
          strokeWidth: 4,
          animation: 'pulse-edge 2s ease-in-out infinite'
        }}
        markerEnd={markerEnd}
      />
    </>
  );
};

// 彩虹边
export const RainbowEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <defs>
        <linearGradient id={`rainbow-gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ff6b6b" />
          <stop offset="16.66%" stopColor="#ffa726" />
          <stop offset="33.33%" stopColor="#ffeb3b" />
          <stop offset="50%" stopColor="#66bb6a" />
          <stop offset="66.66%" stopColor="#42a5f5" />
          <stop offset="83.33%" stopColor="#ab47bc" />
          <stop offset="100%" stopColor="#ff6b6b" />
          <animateTransform
            attributeName="gradientTransform"
            type="rotate"
            values="0;360"
            dur="4s"
            repeatCount="indefinite"
          />
        </linearGradient>
      </defs>
      
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: `url(#rainbow-gradient-${id})`,
          strokeWidth: 5,
          filter: 'drop-shadow(0 0 6px rgba(0, 0, 0, 0.3))'
        }}
        markerEnd={markerEnd}
      />
    </>
  );
};
// FIXME  Mi80OmFIVnBZMlhva3JMbW5iN21ucGM2ZURSSWVBPT06ZWU1NjM4Zjk=

// 电流边
export const ElectricEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) => {
  const [edgePath] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  return (
    <>
      <defs>
        <filter id={`electric-${id}`}>
          <feTurbulence baseFrequency="0.9" numOctaves="4" result="noise" seed="1"/>
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2" />
          <feGaussianBlur stdDeviation="1" result="blur"/>
          <feMerge>
            <feMergeNode in="blur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
        <linearGradient id={`electric-gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#00f2fe" stopOpacity="1" />
          <stop offset="50%" stopColor="#4facfe" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#00f2fe" stopOpacity="1" />
        </linearGradient>
      </defs>
      
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          stroke: `url(#electric-gradient-${id})`,
          strokeWidth: 3,
          filter: `url(#electric-${id})`,
          animation: 'electric-flicker 0.1s infinite alternate'
        }}
        markerEnd={markerEnd}
      />
    </>
  );
};

// 增强默认边
export const EnhancedDefaultEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const edgeType = data?.type || 'default';
  
  const getEdgeStyle = (type: string) => {
    switch (type) {
      case 'primary':
        return {
          stroke: '#1890ff',
          strokeWidth: 3,
          filter: 'drop-shadow(0 0 4px rgba(24, 144, 255, 0.5))'
        };
      case 'success':
        return {
          stroke: '#52c41a',
          strokeWidth: 3,
          filter: 'drop-shadow(0 0 4px rgba(82, 196, 26, 0.5))'
        };
      case 'warning':
        return {
          stroke: '#faad14',
          strokeWidth: 3,
          filter: 'drop-shadow(0 0 4px rgba(250, 173, 20, 0.5))'
        };
      case 'danger':
        return {
          stroke: '#ff4d4f',
          strokeWidth: 3,
          filter: 'drop-shadow(0 0 4px rgba(255, 77, 79, 0.5))'
        };
      default:
        return {
          stroke: '#8c8c8c',
          strokeWidth: 2,
          filter: 'drop-shadow(0 0 2px rgba(0, 0, 0, 0.2))'
        };
    }
  };

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        ...style,
        ...getEdgeStyle(edgeType),
        transition: 'all 0.3s ease'
      }}
      markerEnd={markerEnd}
    />
  );
};

// 边类型映射
export const edgeTypes = {
  animated: AnimatedEdge,
  pulse: PulseEdge,
  rainbow: RainbowEdge,
  electric: ElectricEdge,
  enhanced: EnhancedDefaultEdge,
  default: EnhancedDefaultEdge
};
