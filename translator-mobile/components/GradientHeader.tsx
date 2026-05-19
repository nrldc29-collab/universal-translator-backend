import { Text, StyleSheet } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

interface GradientHeaderProps {
  title: string;
  subtitle?: string;
}

export default function GradientHeader({ title, subtitle }: GradientHeaderProps) {
  return (
    <LinearGradient
      colors={['#06111f', '#082f49', '#020617']}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <Text style={styles.title}>{title}</Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    paddingTop: 40,
    borderBottomLeftRadius: 32,
    borderBottomRightRadius: 32,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.22)',
  },
  title: {
    fontSize: 38,
    fontWeight: "900",
    color: '#f8fafc',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#a5f3fc',
  },
});