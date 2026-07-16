import React from 'react';
import * as Icons from 'lucide-react';

interface IconProps {
  name?: string | null;
  className?: string;
  size?: number;
  color?: string;
}

export const Icon: React.FC<IconProps> = ({ name, className, size = 18, color }) => {
  if (!name) return null;

  // Convert kebab-case or snake_case to PascalCase
  const pascalName = name
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join('');

  // Find the icon component
  let IconComponent = (Icons as any)[pascalName];
  if (!IconComponent) {
    IconComponent = (Icons as any)[name];
  }
  if (!IconComponent) {
    // Fallback: search case-insensitively
    const keys = Object.keys(Icons);
    const matchedKey = keys.find((key) => key.toLowerCase() === name.toLowerCase());
    if (matchedKey) {
      IconComponent = (Icons as any)[matchedKey];
    }
  }

  if (!IconComponent) {
    // If not found, render a generic dot or square
    return <span className={`inline-block w-2 h-2 rounded-full bg-current ${className}`} style={{ width: size, height: size, backgroundColor: color }} />;
  }

  return <IconComponent className={className} size={size} color={color} />;
};

export default Icon;
