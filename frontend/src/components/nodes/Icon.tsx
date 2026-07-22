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

  const trimmed = name.trim();

  // Handle Raw SVGs
  if (trimmed.startsWith('<svg')) {
    return (
      <div
        className={className}
        style={{ width: size, height: size, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        dangerouslySetInnerHTML={{ __html: name }}
      />
    );
  }

  // Handle Custom Image Links/URLs
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('data:image/')) {
    return (
      <img
        src={name}
        alt="icon"
        className={className}
        style={{ width: size, height: size, objectFit: 'contain' }}
      />
    );
  }

  // Tech icon aliases for common backend/database/infrastructure technologies
  const TECH_ALIASES: Record<string, string> = {
    postgres: 'Database',
    postgresql: 'Database',
    redis: 'Zap',
    kafka: 'Rss',
    neo4j: 'Share2',
    memgraph: 'Share2',
    vector: 'Disc',
    pgvector: 'Disc',
    raft: 'Lock',
    claude: 'Bot',
    openai: 'Cpu',
    markdown: 'FileText',
    python: 'Code',
    fastapi: 'Server',
    playwright: 'Play',
    minio: 'HardDrive',
  };

  const lowerName = name.toLowerCase().trim();
  let iconName = TECH_ALIASES[lowerName] || name;

  // Convert kebab-case or snake_case to PascalCase
  const pascalName = iconName
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join('');

  // Find the icon component
  let IconComponent = (Icons as any)[pascalName];
  if (!IconComponent) {
    IconComponent = (Icons as any)[iconName];
  }
  if (!IconComponent) {
    // Fallback: search case-insensitively
    const keys = Object.keys(Icons);
    const matchedKey = keys.find((key) => key.toLowerCase() === iconName.toLowerCase());
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
