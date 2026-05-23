import { TabsTrigger } from './ui/tabs';
import { useTheme } from '../contexts/ThemeContext';
import { ComponentProps } from 'react';

export function ThemedTabTrigger(props: ComponentProps<typeof TabsTrigger>) {
  const { colors } = useTheme();
  const { className, style, ...rest } = props;
  
  return (
    <TabsTrigger
      {...rest}
      className={className}
      style={{
        ...style,
      }}
      data-theme-color={colors.primary}
    />
  );
}
