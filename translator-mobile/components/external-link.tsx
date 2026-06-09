import { openBrowserAsync, WebBrowserPresentationStyle } from 'expo-web-browser';
import { type ComponentProps } from 'react';
import { Linking, Pressable, Text } from 'react-native';

type Props = Omit<ComponentProps<typeof Pressable>, 'onPress'> & {
  href: string;
  children: React.ReactNode;
};

export function ExternalLink({ href, children, ...rest }: Props) {
  return (
    <Pressable
      {...rest}
      onPress={async () => {
        if (process.env.EXPO_OS === 'web') {
          await Linking.openURL(href);
          return;
        }
        await openBrowserAsync(href, {
          presentationStyle: WebBrowserPresentationStyle.AUTOMATIC,
        });
      }}
    >
      {typeof children === 'string' ? <Text>{children}</Text> : children}
    </Pressable>
  );
}
