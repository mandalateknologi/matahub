/**
 * campaign Name/Description Tag Replacement Utilities
 * 
 * Supports custom tags like {YEAR}, {MONTH}, {DATE}, {TIME}, {AUTO}, etc.
 */

let autoIncrementCounter = 1;

export interface TagPreview {
  original: string;
  preview: string;
  tags: string[];
}

/**
 * Get next auto-increment number
 */
export function getNextAutoIncrement(): number {
  return autoIncrementCounter++;
}

/**
 * Reset auto-increment counter
 */
export function resetAutoIncrement(value: number = 1): void {
  autoIncrementCounter = value;
}

/**
 * Get current date/time values for tag replacement
 */
function getDateTimeValues(): Record<string, string> {
  const now = new Date();
  
  return {
    YEAR: now.getFullYear().toString(),
    MONTH: (now.getMonth() + 1).toString().padStart(2, '0'),
    DAY: now.getDate().toString().padStart(2, '0'),
    HOUR: now.getHours().toString().padStart(2, '0'),
    MINUTE: now.getMinutes().toString().padStart(2, '0'),
    SECOND: now.getSeconds().toString().padStart(2, '0'),
    DATE: `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}-${now.getDate().toString().padStart(2, '0')}`,
    TIME: `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`,
    TIMESTAMP: now.getTime().toString(),
    MONTH_NAME: now.toLocaleString('en-US', { month: 'long' }),
    MONTH_SHORT: now.toLocaleString('en-US', { month: 'short' }),
    DAY_NAME: now.toLocaleString('en-US', { weekday: 'long' }),
    DAY_SHORT: now.toLocaleString('en-US', { weekday: 'short' }),
  };
}

/**
 * Get all available tags with their current values
 */
export function getAvailableTags(): Record<string, string> {
  const dateTimeValues = getDateTimeValues();
  
  return {
    ...dateTimeValues,
    AUTO: autoIncrementCounter.toString().padStart(3, '0'),
    AUTO_1: autoIncrementCounter.toString().padStart(1, '0'),
    AUTO_2: autoIncrementCounter.toString().padStart(2, '0'),
    AUTO_3: autoIncrementCounter.toString().padStart(3, '0'),
    AUTO_4: autoIncrementCounter.toString().padStart(4, '0'),
    AUTO_5: autoIncrementCounter.toString().padStart(5, '0'),
  };
}

/**
 * Extract tag names from a template string
 */
export function extractTags(template: string): string[] {
  const tagPattern = /\{([A-Z_0-9]+)\}/g;
  const tags: string[] = [];
  let match;
  
  while ((match = tagPattern.exec(template)) !== null) {
    if (!tags.includes(match[1])) {
      tags.push(match[1]);
    }
  }
  
  return tags;
}

/**
 * Replace tags in a template string with actual values
 */
export function replaceTags(template: string, customValues?: Record<string, string>): string {
  if (!template) return template;
  
  const availableTags = getAvailableTags();
  const allTags = { ...availableTags, ...customValues };
  
  let result = template;
  
  // Replace all tags with their values
  for (const [tag, value] of Object.entries(allTags)) {
    const pattern = new RegExp(`\\{${tag}\\}`, 'g');
    result = result.replace(pattern, value);
  }
  
  return result;
}

/**
 * Generate preview for a template string
 */
export function previewTemplate(template: string, customValues?: Record<string, string>): TagPreview {
  return {
    original: template,
    preview: replaceTags(template, customValues),
    tags: extractTags(template),
  };
}

/**
 * Get tag description/help text
 */
export function getTagDescription(tag: string): string {
  const descriptions: Record<string, string> = {
    YEAR: 'Current year (e.g., 2025)',
    MONTH: 'Current month as number (01-12)',
    DAY: 'Current day of month (01-31)',
    HOUR: 'Current hour (00-23)',
    MINUTE: 'Current minute (00-59)',
    SECOND: 'Current second (00-59)',
    DATE: 'Current date (YYYY-MM-DD)',
    TIME: 'Current time (HH:MM:SS)',
    TIMESTAMP: 'Unix timestamp in milliseconds',
    MONTH_NAME: 'Full month name (e.g., January)',
    MONTH_SHORT: 'Short month name (e.g., Jan)',
    DAY_NAME: 'Full day name (e.g., Monday)',
    DAY_SHORT: 'Short day name (e.g., Mon)',
    AUTO: 'Auto-increment number (001, 002, ...)',
    AUTO_1: 'Auto-increment with 1 digit',
    AUTO_2: 'Auto-increment with 2 digits',
    AUTO_3: 'Auto-increment with 3 digits',
    AUTO_4: 'Auto-increment with 4 digits',
    AUTO_5: 'Auto-increment with 5 digits',
  };
  
  return descriptions[tag] || 'Unknown tag';
}

/**
 * Get all tag help information
 */
export function getAllTagHelp(): Array<{ tag: string; description: string; example: string }> {
  const availableTags = getAvailableTags();
  
  return Object.keys(availableTags).map(tag => ({
    tag,
    description: getTagDescription(tag),
    example: availableTags[tag],
  }));
}

